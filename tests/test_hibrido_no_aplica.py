"""`__no_aplica__` en `hibrido` para Jev, Decisions y OpenRouter.

El proveedor puede declarar «no aplica» un criterio no core; ese criterio
queda sin veredicto y el scoring lo marca en `criterios_sin_evaluar`. Antes
la fila salía con `payload_scoring` y contaba como propuesta validada
aunque el scoring estuviera incompleto (los evaluadores LLM ya lo frenaban,
PR #149). Sin red: transporte simulado.
"""
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

    def test_no_aplica_no_core_frena_la_propuesta(self):
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
                self.assertTrue(r["usar_principal"])
                self.assertFalse(r["permitir_movimientos"])
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


if __name__ == "__main__":
    unittest.main()
