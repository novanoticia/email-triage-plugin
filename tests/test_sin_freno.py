"""Propuesta sin freno de confianza, solo en `comparar` (v3.22.25, informativa).

Diagnóstico real 2026-10-29 (Jev y Decisions, 41 correos): 26-30 criterios
dudosos por correo, probabilidad máxima mediana 0,52; con cualquier umbral
entre 0,8 y 0,3 ningún correo pasaba el freno, así que la comparación de tier
salía siempre vacía. Sin el freno, 12 de 14 daban el mismo tier que el
principal. Sin red: transporte simulado.
"""
import os
import unittest
from unittest.mock import patch

from tests.test_jev import ACTIVO, lote, respuesta
from tests.test_decisions import respuesta as respuesta_decisions
from tests.test_tolerancia_dudas import K, NC, _con_duda
import clasificadores as nc
import decisions as d
import jev as j


class _Base(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"TYPESAFE_API_KEY": "clave-ficticia",
                                           "OPENAI_API_KEY": "clave-ficticia"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.p, self.cfg = lote()

    def comparar(self, transporte, capa=ACTIVO):
        return j.comparar(self.p, self.cfg, capa, transporte)

    def todos_con_confianza_baja(self):
        return _con_duda(list(j._opciones(self.cfg)), incierto=False)


class TestSinFreno(_Base):
    def test_confianza_baja_en_todo_sigue_dando_tier(self):
        # El caso real: el freno descarta el correo, pero el tier se mide.
        r = self.comparar(self.todos_con_confianza_baja())
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "confianza_baja")
        self.assertNotIn("propuesta", fila)
        sf = fila["propuesta_sin_freno"]
        self.assertEqual(set(sf), {"id", "score", "tier"})
        self.assertEqual(r["comparacion"]["total"], 0)
        c = r["comparacion_sin_freno"]
        self.assertEqual(c["total"], 1)
        self.assertEqual(c["mismo_tier"], int(sf["tier"] == fila["principal"]["tier"]))
        self.assertEqual(c["referencia"], "modelo_principal_no_verdad")

    def test_es_la_aritmetica_de_siempre_sobre_los_veredictos(self):
        t = self.todos_con_confianza_baja()
        fila = self.comparar(t)["resultados"][0]
        e = self.p["emails"][0]
        esperado = j._scoring(e["id"], e["control"],
                              fila["evaluacion_jev"]["verdicts"], self.cfg)
        self.assertEqual(fila["propuesta_sin_freno"]["score"], esperado["score"])
        self.assertEqual(fila["propuesta_sin_freno"]["tier"], esperado["tier"])

    def test_sin_dudas_coincide_con_la_propuesta(self):
        fila = self.comparar(respuesta)["resultados"][0]
        self.assertEqual(fila["motivo"], "solo_comparacion")
        self.assertEqual(fila["propuesta_sin_freno"]["score"], fila["propuesta"]["score"])
        self.assertEqual(fila["propuesta_sin_freno"]["tier"], fila["propuesta"]["tier"])

    def test_core_incierto_no_es_comparable(self):
        r = self.comparar(_con_duda([K]))
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "jev_incierto")
        self.assertNotIn("propuesta_sin_freno", fila)
        self.assertEqual(r["comparacion_sin_freno"]["total"], 0)
        self.assertEqual(r["comparacion_sin_freno"]["mismo_tier"], 0)

    def test_incierto_no_core_queda_excluido(self):
        fila = self.comparar(_con_duda([NC]))["resultados"][0]
        self.assertEqual(fila["motivo"], "jev_incierto")
        self.assertIn("propuesta_sin_freno", fila)
        self.assertNotIn(NC, fila["evaluacion_jev"]["verdicts"])

    def test_principal_no_comparable_no_sale_a_la_red_ni_cuenta(self):
        e = self.p["emails"][0]
        e["principal"]["no_aplica"] = {K: "aviso automático"}
        del e["principal"]["verdicts"][K]
        r = self.comparar(respuesta)
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "principal_no_comparable")
        self.assertNotIn("propuesta_sin_freno", fila)
        self.assertEqual(r["comparacion_sin_freno"]["total"], 0)

    def test_no_cambia_lo_que_ya_habia(self):
        r = self.comparar(self.todos_con_confianza_baja())
        for clave in ("comparacion", "comparacion_por_criterio", "sin_propuesta", "cobertura"):
            self.assertIn(clave, r)
        self.assertEqual(r["sin_propuesta"], 1)
        self.assertEqual(r["cobertura"]["propuestas_comparadas"], 0)
        self.assertFalse(r["permitir_movimientos"])

    def test_en_hibrido_no_existe(self):
        for e in self.p["emails"]:
            del e["principal"]
            e["contexto_suficiente"] = True
        r = j.evaluar(self.p, self.cfg, dict(ACTIVO, modo="hibrido"),
                      self.todos_con_confianza_baja())
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "confianza_baja")
        self.assertNotIn("propuesta_sin_freno", fila)
        self.assertNotIn("comparacion_sin_freno", r)
        self.assertTrue(fila["usar_principal"])


class TestDecisions(_Base):
    def test_mismo_campo_en_decisions(self):
        def baja(body, *_):
            r = respuesta_decisions(body)
            for a in r["answers"]:
                n = len(a["probabilities"])
                for pr in a["probabilities"]:
                    pr["probability"] = 0.5 if pr["value"] == a["choice"] else 0.5 / (n - 1)
                a["confidence"] = (0.5 - 1 / n) / (1 - 1 / n)
            return r
        r = d.comparar(self.p, self.cfg, ACTIVO, baja)
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "confianza_baja")
        self.assertIn("propuesta_sin_freno", fila)
        self.assertEqual(r["comparacion_sin_freno"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
