"""Mismo extracto para el especialista (v3.21.30).

Prueba real 2026-10-21 (modo comparar): el principal pasó a Haiku los
extractos «algo más cortos que los que usé yo (quité algunas frases)», y
la comparación salió sesgada sin que nada lo marcase. `sanitizar` devuelve
ahora `huella_extracto`; con ella en `esperados` y el `lote` enviado,
`validar` marca `extracto_distinto`. Sin red; datos sintéticos.
"""
import copy
import unittest

from tests import DIR_SCRIPTS  # noqa: F401  (pone scripts en sys.path)
import modelos as m
import triage_helpers as th
from tests.test_modelos import lote

CUERPO = ("La reunión del comité se adelanta al jueves. Trae el informe "
          "revisado y las cifras del segundo trimestre. ") * 40


class TestHuellaEnSanitizar(unittest.TestCase):
    def test_la_huella_es_la_del_texto_devuelto(self):
        r = th.cmd_sanitizar(CUERPO, max_chars=300)
        self.assertTrue(r["texto"].endswith(" [truncado]"))
        self.assertEqual(r["huella_extracto"], th.huella_extracto(r["texto"]))
        self.assertEqual(len(r["huella_extracto"]), 16)

    def test_longitud_final_no_cambia_de_significado(self):
        r = th.cmd_sanitizar(CUERPO, max_chars=300)
        self.assertEqual(r["longitud_final"],
                         len(r["texto"]) - len(" [truncado]"))

    def test_recortar_cambia_la_huella(self):
        t = th.cmd_sanitizar(CUERPO, max_chars=300)["texto"]
        self.assertNotEqual(th.huella_extracto(t), th.huella_extracto(t[:-40]))


class TestValidarExtracto(unittest.TestCase):
    def setUp(self):
        self.extracto = th.cmd_sanitizar(CUERPO, max_chars=300)["texto"]
        self.p = lote()
        self.p["esperados"][0]["huella_extracto"] = \
            th.huella_extracto(self.extracto)

    def _con_lote(self, extracto):
        self.p["lote"] = {"unidades": [{"id": "1", "extracto": extracto}]}
        return m.ejecutar("validar", self.p)

    def test_mismo_extracto_cuenta(self):
        r = self._con_lote(self.extracto)
        self.assertTrue(r["ok"])
        self.assertIn("resultado", r["resultados"][0])

    def test_el_caso_real_extracto_recortado(self):
        r = self._con_lote(self.extracto[:200])
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "extracto_distinto")
        self.assertTrue(fila["usar_principal"])
        self.assertNotIn("resultado", fila)

    def test_huella_sin_lote_no_cuenta(self):
        r = m.ejecutar("validar", self.p)
        self.assertEqual(r["resultados"][0]["motivo"], "extracto_distinto")

    def test_unidad_ausente_del_lote_no_cuenta(self):
        self.p["lote"] = {"unidades": [{"id": "9", "extracto": self.extracto}]}
        r = m.ejecutar("validar", self.p)
        self.assertEqual(r["resultados"][0]["motivo"], "extracto_distinto")

    def test_huella_no_texto_no_cuenta(self):
        self.p["esperados"][0]["huella_extracto"] = 123
        r = self._con_lote(self.extracto)
        self.assertEqual(r["resultados"][0]["motivo"], "extracto_distinto")

    def test_lote_mal_formado(self):
        for malo in ([], "x", {"unidades": []}, {"unidades": [{"id": 1}]},
                     {"otra": 1}):
            self.p["lote"] = malo
            self.assertEqual(m.ejecutar("validar", self.p)["motivo"],
                             "lote_invalido", malo)

    def test_sin_huella_se_comporta_como_antes(self):
        p = lote()
        p["lote"] = {"unidades": [{"id": "1", "extracto": "otro texto"}]}
        r = m.ejecutar("validar", p)
        self.assertIn("resultado", r["resultados"][0])
        self.assertIn("resultado", m.ejecutar("validar", lote())
                      ["resultados"][0])

    def test_no_muta_la_entrada(self):
        self.p["lote"] = {"unidades": [{"id": "1", "extracto": self.extracto}]}
        copia = copy.deepcopy(self.p)
        m.ejecutar("validar", self.p)
        self.assertEqual(self.p, copia)


if __name__ == "__main__":
    unittest.main()
