"""Cobertura de criterios: no basta con los core si el config pide todos (v3.21.40).

Prueba real 2026-10-24: «para comparar bien habría que evaluar los 30
criterios activos. Yo evalué solo los 13 core, así que no delegué». El
script compara los criterios evaluados con los activos del config (solo los
core si la capa veloz lo pide), lo marca, avisa en el lote y en el informe,
y `registrar` no acepta ese movimiento como triaje. Sin red; tempfiles.
"""
import copy
import os
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

if DIR_SCRIPTS not in sys.path:
    sys.path.insert(0, DIR_SCRIPTS)
import triage_helpers as th  # noqa: E402

CFG = {
    "criterios_epistemicos": {
        "core1": {"activo": True, "core": True, "eje": "valor_decisional",
                  "si": 2, "no": -2},
        "core2": {"activo": True, "core": True, "eje": "valor_decisional",
                  "si": 2, "no": -2},
        "extra": {"activo": True, "core": False, "eje": "valor_decisional",
                  "si": 1, "no": 0},
        "apagado": {"activo": False, "core": False, "eje": "valor_decisional",
                    "si": 1, "no": 0},
    },
    "scoring": {"ejes": {"valor_decisional": [-10, 10]}},
    "tiers": {"reply_needed": 10, "review": 4, "reading_later": 0,
              "archive": -1},
}
SOLO_CORE = {"core1": "si", "core2": "si"}
TODOS = dict(SOLO_CORE, extra="si")
SID = "20261025-082342"


class TestCoberturaScoring(unittest.TestCase):
    def test_el_caso_real_solo_los_core(self):
        r = th.cmd_scoring({"verdicts": SOLO_CORE}, CFG)
        self.assertEqual(r["criterios_sin_evaluar"], ["extra"])
        self.assertEqual(r["score"], 4)  # no cambia score ni tier

    def test_todos_evaluados_no_añade_nada(self):
        r = th.cmd_scoring({"verdicts": TODOS}, CFG)
        self.assertNotIn("criterios_sin_evaluar", r)

    def test_inactivos_no_cuentan(self):
        r = th.cmd_scoring({"verdicts": TODOS}, CFG)
        self.assertNotIn("apagado", r.get("criterios_sin_evaluar", []))

    def test_en_modo_veloz_bastan_los_core(self):
        cfg = copy.deepcopy(CFG)
        cfg["comportamiento_veloz"] = {"solo_criterios_core": True}
        self.assertNotIn("criterios_sin_evaluar",
                         th.cmd_scoring({"verdicts": SOLO_CORE}, cfg))
        r = th.cmd_scoring({"verdicts": {"core1": "si"}}, cfg)
        self.assertEqual(r["criterios_sin_evaluar"], ["core2"])

    def test_veredicto_invalido_cuenta_como_no_evaluado(self):
        r = th.cmd_scoring({"verdicts": dict(TODOS, extra="quizas")}, CFG)
        self.assertEqual(r["criterios_sin_evaluar"], ["extra"])

    def test_lote_y_brief(self):
        lote = {"emails": [{"id": 1, "verdicts": SOLO_CORE},
                           {"id": 2, "verdicts": TODOS}]}
        r = th.cmd_scoring_dispatch(lote, CFG, brief=True)
        self.assertEqual(r["alerta_cobertura"]["ids"], [1])
        self.assertEqual(r["resultados"][0]["criterios_sin_evaluar"], ["extra"])
        self.assertNotIn("alerta_cobertura",
                         th.cmd_scoring_dispatch({"emails": [lote["emails"][1]]}, CFG))


class TestCoberturaFrenos(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.d.name
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))

    def test_registrar_no_acepta_el_movimiento_como_triaje(self):
        ruta = os.path.join(self.d.name, "session_log.jsonl")
        r = th.cmd_registrar(ruta, {
            "session_id": SID, "to_folder": "ARCHIVE-TRIAGE", "score": 4,
            "modo_scoring": "determinista", "criterios_sin_evaluar": ["extra"]})
        self.assertFalse(r["ok"])
        self.assertTrue(r["bloquea_movimiento"])
        r = th.cmd_registrar(ruta, {
            "session_id": SID, "to_folder": "ARCHIVE-TRIAGE", "score": 4,
            "modo_scoring": "determinista", "criterios_sin_evaluar": []})
        self.assertTrue(r["ok"], r)

    def test_el_informe_lo_avisa_por_la_ultima_pasada(self):
        ruta = os.path.join(self.d.name, "desgloses", SID + ".jsonl")
        for verdicts in (SOLO_CORE, None):
            lote = {"emails": [{"id": 1, "verdicts": SOLO_CORE},
                               {"id": 2, "verdicts": verdicts or TODOS}]}
            th.cmd_registrar(ruta, {"ts": "x", "desglose":
                                    th.cmd_scoring_dispatch(lote, CFG)})
        r = th.cmd_informe({"session_id": SID, "modo": "simulacion",
                            "modo_scoring": "determinista", "unidades": [
                                {"n": 1, "tier": "REVIEW", "score": 4,
                                 "asunto": "A", "mids": ["<m>"]}]})
        self.assertEqual(r["criterios_sin_evaluar"], 1)  # el 2 se completó
        with open(r["ruta"], encoding="utf-8") as fh:
            self.assertIn("Criterios sin evaluar en 1 correos", fh.read())

    def test_sin_desglose_el_informe_no_cambia(self):
        r = th.cmd_informe({"session_id": SID, "modo": "simulacion",
                            "modo_scoring": "determinista", "unidades": [
                                {"n": 1, "tier": "REVIEW", "score": 4,
                                 "asunto": "A", "mids": ["<m>"]}]})
        self.assertNotIn("criterios_sin_evaluar", r)


if __name__ == "__main__":
    unittest.main()
