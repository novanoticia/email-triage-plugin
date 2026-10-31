"""`__no_aplica__` en `hibrido` para Jev, Decisions y OpenRouter.

El proveedor puede declarar «no aplica» un criterio no core; ese criterio
queda sin veredicto y el scoring lo marca en `criterios_sin_evaluar`.
v3.24.1: la fila ya no cuenta como validada con el scoring incompleto
(`scoring_incompleto`). v3.24.4: si el criterio tiene una sola opción a 0
puntos y puntuarla da el mismo score y tier que excluirlo, se puntúa así
(`no_aplica_puntuado_como`); si no, el freno sigue. Sin red: transporte
simulado.
"""
import copy
import os
import unittest
from unittest.mock import patch

from tests.test_core_no_aplica_comparar import cfg_ensayo
from tests.test_decisions import respuesta as respuesta_decisions
from tests.test_jev import ACTIVO, lote, respuesta as respuesta_jev
from tests.test_openrouter import respuesta as respuesta_openrouter
from tests.test_tolerancia_dudas import NC
import clasificadores as nc
import decisions as d
import jev as j
import openrouter as o


def _jev_no_aplica(base):
    def t(body, *_):
        r = base(body)
        r["answers"][NC].update(choice=nc.NO_APLICA, probabilities={
            x: float(x == nc.NO_APLICA) for x in r["answers"][NC]["probabilities"]})
        return r
    return t


def _decisions_no_aplica(body, *_):
    r = respuesta_decisions(body)
    for a in r["answers"]:
        if a["name"] == NC:
            a["choice"] = nc.NO_APLICA
            a["probabilities"] = [{"value": x["value"],
                                   "probability": float(x["value"] == nc.NO_APLICA)}
                                  for x in a["probabilities"]]
    return r


PROVEEDORES = (("jev", j, _jev_no_aplica(respuesta_jev), respuesta_jev),
               ("decisions", d, _decisions_no_aplica, respuesta_decisions),
               ("openrouter", o, _jev_no_aplica(respuesta_openrouter), respuesta_openrouter))


class TestHibridoNoAplica(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"TYPESAFE_API_KEY": "clave-ficticia",
                                      "OPENAI_API_KEY": "clave-ficticia",
                                      "OPENROUTER_API_KEY": "clave-ficticia"})
        env.start()
        self.addCleanup(env.stop)
        self.cfg = cfg_ensayo()
        self.assertFalse(nc._opciones(self.cfg)[NC][1], "NC debe ser no core")

    def hibrido(self, mod, transporte):
        p, _ = lote()
        for e in p["emails"]:
            e.pop("principal", None)
            e["contexto_suficiente"] = True
        return mod.evaluar(p, self.cfg, dict(ACTIVO, modo="hibrido"), transporte)

    def test_no_aplica_con_opcion_a_cero_se_puntua_asi(self):
        cero = [o for o in sorted(nc._opciones(self.cfg)[NC][0])
                if self.cfg["criterios_epistemicos"][NC][o] == 0]
        self.assertEqual(len(cero), 1)
        for nombre, mod, transporte, _ in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                r = self.hibrido(mod, transporte)
                self.assertTrue(r["ok"], r)
                fila = r["resultados"][0]
                self.assertIn(fila["motivo"], ("propuesta_validada",
                                               "reevaluar_tier_umbral_o_confianza"))
                self.assertEqual(fila["no_aplica_puntuado_como"], {NC: cero[0]})
                self.assertIn(NC, fila["no_aplica"])
                self.assertEqual(fila["payload_scoring"]["verdicts"][NC], cero[0])
                self.assertFalse(fila["propuesta"].get("criterios_sin_evaluar"))
                self.assertEqual(r["cobertura"]["propuestas_validadas"], 1)
                self.assertFalse(r["permitir_movimientos"])

    def test_no_aplica_sin_una_sola_opcion_a_cero_frena(self):
        cfg = copy.deepcopy(self.cfg)
        c = cfg["criterios_epistemicos"][NC]
        for o in nc._opciones(cfg)[NC][0]:
            c[o] = 0  # todas a 0: no hay una única opción equivalente
        self.cfg = cfg
        for nombre, mod, transporte, _ in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                r = self.hibrido(mod, transporte)
                self.assertTrue(r["ok"], r)
                fila = r["resultados"][0]
                self.assertEqual(fila["motivo"], "scoring_incompleto")
                self.assertIn(NC, fila["no_aplica"])
                self.assertTrue(fila["usar_principal"])
                self.assertNotIn("propuesta", fila)
                self.assertNotIn("payload_scoring", fila)
                self.assertNotIn("no_aplica_puntuado_como", fila)
                self.assertEqual(r["cobertura"]["propuestas_validadas"], 0)
                self.assertEqual(r["cobertura"]["pendientes_principal"], 1)
                self.assertEqual(r["sin_propuesta"], 1)


    def test_sin_no_aplica_sigue_igual(self):
        for nombre, mod, _, transporte in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                fila = self.hibrido(mod, transporte)["resultados"][0]
                self.assertIn(fila["motivo"], ("propuesta_validada",
                                               "reevaluar_tier_umbral_o_confianza"))
                self.assertIn("payload_scoring", fila)
                self.assertFalse(fila["propuesta"].get("criterios_sin_evaluar"))

    def test_comparar_no_cambia(self):
        for nombre, mod, transporte, _ in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                p, _ = lote()
                activos = nc._opciones(self.cfg)
                for e in p["emails"]:
                    e["principal"] = {"verdicts": {k: sorted(v[0])[0] for k, v in activos.items()},
                                      "no_aplica": {}}
                fila = mod.comparar(p, self.cfg, ACTIVO, transporte)["resultados"][0]
                self.assertEqual(fila["motivo"], "solo_comparacion")
                self.assertIn(NC, fila["propuesta"]["criterios_sin_evaluar"])


class TestNoAplicaACero(unittest.TestCase):
    """La conversión solo ocurre si no cambia nada del scoring."""
    CONTROL = {"hard_rules": [], "extra_points": 0, "forzar_reply_needed": False,
               "tier_maximo": None, "remitente_en_historial": False}

    def setUp(self):
        self.cfg = cfg_ensayo()
        self.activos = nc._opciones(self.cfg)
        self.v = {k: sorted(o)[0] for k, (o, _) in self.activos.items() if k != NC}

    def convertir(self, no_aplica):
        return nc._no_aplica_a_cero("1", self.CONTROL, self.v, no_aplica, self.activos, self.cfg)

    def test_mismo_score_y_tier_que_la_exclusion(self):
        completos, convertidos, propuesta = self.convertir([NC])
        excluida = nc._scoring("1", self.CONTROL, self.v, self.cfg)
        self.assertEqual((propuesta["score"], propuesta["tier"]),
                         (excluida["score"], excluida["tier"]))
        self.assertEqual(set(completos), set(self.activos))
        self.assertEqual(list(convertidos), [NC])

    def test_si_el_scoring_cambia_no_convierte(self):
        real = nc._scoring

        def distinto(ident, control, vs, cfg):
            r = dict(real(ident, control, vs, cfg))
            if NC in vs:
                r["score"] = r["score"] + 1
            return r
        with patch.object(nc, "_scoring", side_effect=distinto):
            self.assertIsNone(self.convertir([NC]))

    def test_core_o_desconocido_no_convierte(self):
        core = next(k for k, (_, c) in self.activos.items() if c)
        self.assertIsNone(self.convertir([core]))
        self.assertIsNone(self.convertir(["criterio_inexistente"]))
        self.assertIsNone(self.convertir([]))


if __name__ == "__main__":
    unittest.main()
