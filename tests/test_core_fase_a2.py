#!/usr/bin/env python3
"""Tests de la fachada core (Fase A.2, split seguro). Aditivo, sin tocar motor."""
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import tests  # noqa: E402,F401  (su __init__ pone scripts/ en sys.path)

import core  # noqa: E402
import triage_helpers as th  # noqa: E402


class TestFachadaCore(unittest.TestCase):
    def test_reexporta_las_mismas_funciones(self):
        # La fachada NO reimplementa: apunta al mismo objeto del motor.
        self.assertIs(core.scoring, th.cmd_scoring)
        self.assertIs(core.sanitizar, th.cmd_sanitizar)
        self.assertIs(core.agrupar_hilos, th.cmd_agrupar_hilos)
        self.assertIs(core.validar_config, th.cmd_validar_config)

    def test_all_completo(self):
        for nombre in core.__all__:
            self.assertTrue(hasattr(core, nombre), nombre)

    def test_scoring_via_core_funciona(self):
        cfg = {"criterios": {"cambia_algo_concreto":
               {"activo": True, "eje": "valor_decisional",
                "veredictos": {"si": 3, "no": 0}}},
               "tiers": {}, "ejes": {}}
        out = core.scoring({"verdicts": {"cambia_algo_concreto": "si"}}, cfg)
        self.assertIn("score", out)


if __name__ == "__main__":
    unittest.main()
