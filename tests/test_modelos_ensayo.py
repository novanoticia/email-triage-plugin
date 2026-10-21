"""validar y la capa del ensayo P3 (v3.21.31).

Prueba real 2026-10-21 (modo comparar con `ensayo_p3` activo): Haiku
evaluó los criterios efectivos (la capa desactiva tres y añade sus
sustitutos), pero `modelos.py validar` no aceptaba `--config-ensayo` y
comprobaba contra los del config base: `cobertura_incompleta` siempre.
"""
import copy
import json
import os
import subprocess
import sys
import unittest

from tests import DIR_SCRIPTS
import modelos as m
import triage_helpers as th
from tests.test_modelos import PLAN_OK

SKILL = os.path.dirname(DIR_SCRIPTS)
CONFIG = os.path.join(SKILL, "config.yaml")
ENSAYO = os.path.join(SKILL, "config-ensayo-p3.yaml")


def _payload(cfg):
    activos = m._criterios(cfg)
    vs = {k: next(iter(opciones)) for k, (opciones, _) in activos.items()}
    return {"plan": copy.deepcopy(PLAN_OK), "esperados": [{"id": "1", "control": {
        "hard_rules": [], "extra_points": 0, "forzar_reply_needed": False,
        "tier_maximo": None, "remitente_en_historial": False}}],
        "respuesta": {"evaluaciones": [{"id": "1", "verdicts": vs,
            "no_aplica": {}, "evidencias": {k: "Evidencia sintética." for k in vs},
            "dudas": [], "resumen": "Resumen sintético."}]}}


class TestValidarConEnsayo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = th._cargar_config(CONFIG)
        cls.cfg_ensayo = th._fusiona_config_ensayo(base, ENSAYO)
        cls.p = _payload(cls.cfg_ensayo)
        # El ensayo cambia de verdad los criterios activos.
        assert set(m._criterios(base)) != set(m._criterios(cls.cfg_ensayo))

    def _cli(self, *extra):
        r = subprocess.run([sys.executable, os.path.join(DIR_SCRIPTS, "modelos.py"),
                            "validar", *extra], input=json.dumps(self.p),
                           text=True, capture_output=True)
        return json.loads(r.stdout)

    def test_sin_la_capa_reproduce_el_fallo_real(self):
        r = self._cli("--config", CONFIG)
        self.assertEqual(r["resultados"][0]["motivo"],
                         "cobertura_incompleta_o_desconocida")

    def test_con_la_capa_la_respuesta_cuenta(self):
        r = self._cli("--config", CONFIG, "--config-ensayo", ENSAYO)
        self.assertTrue(r["ok"], r)
        self.assertIn("resultado", r["resultados"][0])

    def test_ensayo_sin_config_base_se_rechaza(self):
        self.assertEqual(self._cli("--config-ensayo", ENSAYO)["motivo"],
                         "entrada_o_config_invalida")

    def test_capa_inexistente_es_no_op(self):
        r = self._cli("--config", CONFIG, "--config-ensayo", "/no/existe.yaml")
        self.assertEqual(r["resultados"][0]["motivo"],
                         "cobertura_incompleta_o_desconocida")


if __name__ == "__main__":
    unittest.main()
