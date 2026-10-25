"""Exención de `sender_bulk_penalizacion` por config, no por el modelo (v3.21.38).

Pruebas reales 2026-10-24: «las Codex de tu propio repo no llevan
penalización de sender masivo. Es una decisión mía; el script no lo exige».
Ahora la decide la persona en `filtros.remitentes_sin_penalizacion_masiva` y
el script la aplica por el `remitente` del payload. Sin red.
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
        "a": {"activo": True, "core": True, "eje": "valor_decisional",
              "si": 5, "no": -5}},
    "scoring": {"ejes": {"valor_decisional": [-10, 10]}},
    "tiers": {"reply_needed": 10, "review": 4, "reading_later": 0,
              "archive": -1},
    "hard_rules": {"sender_bulk_penalizacion": -4},
    "filtros": {"remitentes_sin_penalizacion_masiva": ["notifications@github.com"]},
}
CODEX = "chatgpt-codex-connector[bot] <notifications@github.com>"
BASE = {"verdicts": {"a": "si"}, "hard_rules": ["sender_bulk_penalizacion"]}


def _p(**extra):
    p = copy.deepcopy(BASE)
    p.update(extra)
    return p


class TestSinPenalizacionMasiva(unittest.TestCase):
    def test_el_caso_real_codex_no_se_penaliza(self):
        r = th.cmd_scoring(_p(remitente=CODEX), CFG)
        self.assertEqual(r["score"], 5)
        self.assertEqual(r["hard_puntos"], 0)
        self.assertIs(r["sender_bulk_exento"], True)

    def test_el_resto_sigue_penalizado(self):
        r = th.cmd_scoring(_p(remitente="news@aeon.co"), CFG)
        self.assertEqual(r["score"], 1)
        self.assertIs(r["sender_bulk_exento"], False)

    def test_el_nombre_visible_no_basta(self):
        r = th.cmd_scoring(_p(remitente="notifications@github.com <x@spam.io>"), CFG)
        self.assertEqual(r["score"], 1)

    def test_sin_remitente_manda_lo_que_traiga_el_modelo(self):
        r = th.cmd_scoring(_p(), CFG)
        self.assertEqual(r["score"], 1)
        self.assertIsNone(r["sender_bulk_exento"])

    def test_sin_lista_nada_cambia(self):
        cfg = copy.deepcopy(CFG)
        del cfg["filtros"]
        r = th.cmd_scoring(_p(remitente=CODEX), cfg)
        self.assertEqual(r["score"], 1)
        self.assertNotIn("sender_bulk_exento", r)

    def test_otras_reglas_se_conservan_y_brief_lo_lleva(self):
        cfg = copy.deepcopy(CFG)
        cfg["hard_rules"]["mencion_directa_boost"] = 3
        lote = {"emails": [_p(id=1, remitente=CODEX,
                              hard_rules=["sender_bulk_penalizacion",
                                          "mencion_directa_boost"])]}
        r = th.cmd_scoring_dispatch(lote, cfg, brief=True)["resultados"][0]
        self.assertEqual(r["score"], 8)
        self.assertIs(r["sender_bulk_exento"], True)

    def test_validar_config_avisa_de_entradas_invalidas(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML no instalado")
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "config.yaml")
            with open(os.path.join(DIR_SCRIPTS, "..", "config.yaml"),
                      encoding="utf-8") as fh:
                texto = fh.read()
            texto = texto.replace(
                "remitentes_sin_penalizacion_masiva: []",
                'remitentes_sin_penalizacion_masiva: ["GitHub"]', 1)
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(texto)
            r = th.cmd_validar_config(ruta)
        self.assertIn("GitHub", " ".join(r.get("avisos", [])))


if __name__ == "__main__":
    unittest.main()
