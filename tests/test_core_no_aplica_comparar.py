"""Core que admite `__no_aplica__`, solo en `comparar` (v3.22.26).

Diagnóstico real 2026-10-29 (Jev y Decisions con el ensayo P3): 12 de 13
filas `principal_no_comparable` venían de un solo criterio,
`razonamiento_dirigido`, que el principal declaraba «no aplica» en avisos y
boletines; al proveedor no se le ofrecía esa opción por ser core. Sin red:
transporte simulado; prueban el mecanismo, no la calidad del proveedor.
"""
import os
import unittest
from unittest.mock import patch

import yaml

from tests.test_jev import ACTIVO, SKILL, lote, respuesta
from tests.test_decisions import respuesta as respuesta_decisions
from tests.test_tolerancia_dudas import K, NC
import clasificadores as nc
import decisions as d
import jev as j
import triage_helpers as th

R = "razonamiento_dirigido"  # core del ensayo P3


def cfg_ensayo():
    cfg = yaml.safe_load((SKILL / "config.yaml").read_text())
    return th._fusiona_config_ensayo(cfg, str(SKILL / "config-ensayo-p3.yaml"))


def _con_no_aplica(criterios, base=respuesta):
    def t(body, *_):
        r = base(body)
        for k in criterios:
            r["answers"][k].update(choice=nc.NO_APLICA, probabilities={
                o: float(o == nc.NO_APLICA) for o in r["answers"][k]["probabilities"]})
        return r
    return t


class _Base(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"TYPESAFE_API_KEY": "clave-ficticia",
                                           "OPENAI_API_KEY": "clave-ficticia"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.p, _ = lote()
        self.cfg = cfg_ensayo()
        self.activos = j._opciones(self.cfg)
        for e in self.p["emails"]:
            e["principal"] = {"verdicts": {k: sorted(v[0])[0] for k, v in self.activos.items()},
                              "no_aplica": {}}

    def principal_no_aplica(self, k):
        e = self.p["emails"][0]
        del e["principal"]["verdicts"][k]
        e["principal"]["no_aplica"] = {k: "aviso automático sin decisión"}

    def comparar(self, transporte=respuesta):
        return j.comparar(self.p, self.cfg, ACTIVO, transporte)

    def preguntas_enviadas(self, modo):
        enviadas = []

        def t(body, *_):
            enviadas.append(body["questions"])
            return respuesta(body)
        if modo == "hibrido":
            for e in self.p["emails"]:
                del e["principal"]
                e["contexto_suficiente"] = True
            j.evaluar(self.p, self.cfg, dict(ACTIVO, modo="hibrido"), t)
        else:
            self.comparar(t)
        return enviadas[0]


class TestPreguntas(_Base):
    def test_comparar_ofrece_no_aplica_solo_a_ese_core(self):
        self.assertTrue(self.activos[R][1] and self.activos[K][1])
        q = self.preguntas_enviadas("comparar")
        self.assertIn(nc.NO_APLICA, q[R]["criteria"])
        self.assertNotIn(nc.NO_APLICA, q[K]["criteria"])
        self.assertIn(nc.NO_APLICA, q[NC]["criteria"])

    def test_hibrido_no_cambia(self):
        q = self.preguntas_enviadas("hibrido")
        self.assertNotIn(nc.NO_APLICA, q[R]["criteria"])

    def test_sin_el_ensayo_las_preguntas_no_cambian(self):
        cfg = yaml.safe_load((SKILL / "config.yaml").read_text())
        activos = nc._opciones(cfg)
        self.assertNotIn(R, activos)
        self.assertEqual(nc.preguntas_neutras(cfg, nc._activos_para_preguntas(activos, "comparar")),
                         nc.preguntas_neutras(cfg, activos))

    def test_decisions_ofrece_lo_mismo(self):
        enviadas = []

        def t(body, *_):
            enviadas.append({q["name"]: {c["value"] for c in q["choices"]}
                             for q in body["questions"]})
            return respuesta_decisions(body)
        d.comparar(self.p, self.cfg, ACTIVO, t)
        self.assertIn(nc.NO_APLICA, enviadas[0][R])
        self.assertNotIn(nc.NO_APLICA, enviadas[0][K])


class TestComparable(_Base):
    def test_los_dos_dicen_no_aplica_y_coinciden(self):
        self.principal_no_aplica(R)
        r = self.comparar(_con_no_aplica([R]))
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "solo_comparacion", fila)
        self.assertIn("tier", fila["principal"])
        self.assertIn(R, fila["no_aplica"])
        self.assertNotIn(R, fila["por_criterio"]["difieren"])
        self.assertEqual(r["comparacion"]["total"], 1)
        self.assertEqual(r["comparacion_sin_freno"]["total"], 1)

    def test_principal_no_aplica_y_proveedor_opina_es_comparable(self):
        self.principal_no_aplica(R)
        fila = self.comparar()["resultados"][0]
        self.assertEqual(fila["motivo"], "solo_comparacion")
        self.assertEqual(fila["por_criterio"]["difieren"][R]["principal"], nc.NO_APLICA)

    def test_solo_el_proveedor_dice_no_aplica(self):
        fila = self.comparar(_con_no_aplica([R]))["resultados"][0]
        self.assertEqual(fila["motivo"], "solo_comparacion")
        self.assertEqual(fila["por_criterio"]["difieren"][R]["externo"], nc.NO_APLICA)
        aceptados = th._veredictos_aceptados(fila["propuesta"])
        self.assertTrue(aceptados)
        self.assertNotIn(R, aceptados)

    def test_otro_core_no_aplica_sigue_fuera(self):
        self.principal_no_aplica(K)
        fila = self.comparar()["resultados"][0]
        self.assertEqual(fila["motivo"], "principal_no_comparable")
        self.assertIsNone(fila["principal"])

    def test_core_incierto_sigue_frenando(self):
        def t(body, *_):
            r = respuesta(body)
            r["answers"][R].update(choice=nc.INCIERTO, probabilities={
                o: float(o == nc.INCIERTO) for o in r["answers"][R]["probabilities"]})
            return r
        fila = self.comparar(t)["resultados"][0]
        self.assertEqual(fila["motivo"], "jev_incierto")
        self.assertNotIn("propuesta_sin_freno", fila)


class TestTolerancia(_Base):
    def test_la_exclusion_entra_en_las_combinaciones_solo_en_comparar(self):
        e = self.p["emails"][0]
        v = {"verdicts": dict(e["principal"]["verdicts"]), "inciertos": []}
        n = len(self.activos[R][0])
        fijo = {"tier": "REVIEW", "score": 5}
        for modo, esperadas in (("comparar", n + 1), ("hibrido", n), (None, n)):
            with self.subTest(modo=modo), patch.object(nc, "_scoring", return_value=fijo) as s:
                r = nc._dudas_irrelevantes(e, v, [R], self.activos, self.cfg, 3, modo)
                self.assertEqual(r["combinaciones"], esperadas)
                self.assertEqual(s.call_count, esperadas)
                # La exclusión es la combinación sin el criterio.
                self.assertEqual(any(R not in c.args[2] for c in s.call_args_list),
                                 modo == "comparar")


if __name__ == "__main__":
    unittest.main()
