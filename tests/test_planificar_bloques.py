"""Evaluación por bloques (v3.22.14, opt-in con `scoring.bloques: true`).

`planificar-bloques` reparte las unidades en bloques equilibrados de como
mucho `scoring.tamano_bloque`; con bloques activos, `scoring` (CLI) rechaza
un lote mayor o sin `--desglose-append`. Sin el flag, nada cambia. Sin red;
tempfiles.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests import DIR_SCRIPTS
from tests.test_huellas_plantilla import CFG, plantilla_con_retoques
import triage_helpers as th

SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")


def cfg_bloques(activo=True, tam=None):
    cfg = copy.deepcopy(CFG)
    cfg.setdefault("scoring", {})["bloques"] = activo
    if tam is not None:
        cfg["scoring"]["tamano_bloque"] = tam
    return cfg


def lote(n):
    vs = (plantilla_con_retoques() * 3)[:n]
    return {"emails": [{"id": "m%02d" % i, "verdicts": v}
                       for i, v in enumerate(vs, 1)]}


class TestPlanificar(unittest.TestCase):
    def test_reparte_equilibrado_y_en_orden(self):
        ids = ["m%02d" % i for i in range(23)]
        out = th.cmd_planificar_bloques({"ids": ids}, cfg_bloques())
        self.assertTrue(out["ok"])
        self.assertEqual([len(b["ids"]) for b in out["bloques"]], [8, 8, 7])
        self.assertEqual([i for b in out["bloques"] for i in b["ids"]], ids)
        self.assertEqual([b["bloque"] for b in out["bloques"]], [1, 2, 3])
        self.assertNotIn("aviso", out)

    def test_tamano_del_config_y_su_defecto(self):
        ids = list(range(12))
        self.assertEqual(len(th.cmd_planificar_bloques(
            {"ids": ids}, cfg_bloques(tam=4))["bloques"]), 3)
        for raro in (1, 26, "diez", True, 3.5):
            out = th.cmd_planificar_bloques({"ids": ids}, cfg_bloques(tam=raro))
            self.assertEqual(out["tamano"], th.TAMANO_BLOQUE_DEF)
        self.assertEqual(len(th.cmd_planificar_bloques(
            {"ids": [1, 2, 3]}, cfg_bloques())["bloques"]), 1)

    def test_sin_flag_planifica_pero_avisa(self):
        out = th.cmd_planificar_bloques({"ids": [1, 2]}, CFG)
        self.assertFalse(out["activo"])
        self.assertIn("aviso", out)
        # Solo un true literal activa.
        self.assertFalse(th._config_bloques(cfg_bloques(activo="si"))[0])

    def test_entradas_invalidas(self):
        for datos in (None, [], {}, {"ids": []}, {"ids": "m1"},
                      {"ids": [1, 1]}, {"ids": [{"a": 1}]}, {"ids": [True]}):
            out = th.cmd_planificar_bloques(datos, cfg_bloques())
            self.assertIs(out["ok"], False, datos)
        self.assertTrue(th.cmd_planificar_bloques({"ids": [1]}, None)["ok"])


class TestReglaScoring(unittest.TestCase):
    def test_sin_flag_no_niega_nada(self):
        self.assertIsNone(th._regla_bloques(lote(30), CFG, False))

    def test_con_flag_exige_desglose_y_tamano(self):
        cfg = cfg_bloques()
        self.assertIn("--desglose-append",
                      th._regla_bloques(lote(5), cfg, False)["error"])
        self.assertIn("como mucho 10",
                      th._regla_bloques(lote(11), cfg, True)["error"])
        self.assertIsNone(th._regla_bloques(lote(10), cfg, True))
        # Un correo suelto cuenta como uno, pero también acumula.
        uno = lote(1)["emails"][0]
        self.assertIsNone(th._regla_bloques(uno, cfg, True))
        self.assertIsNotNone(th._regla_bloques(uno, cfg, False))

    def test_cli_rechaza_sin_escribir_y_acepta_el_bloque(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.yaml")
            with open(cfg, "w") as fh:
                json.dump(cfg_bloques(), fh)   # JSON es YAML válido
            ruta = os.path.join(d, "s.jsonl")

            def scoring(payload, *extra):
                r = subprocess.run([sys.executable, SCRIPT, "scoring",
                                    "--config", cfg, *extra],
                                   input=json.dumps(payload),
                                   capture_output=True, text=True)
                return json.loads(r.stdout)

            grande = scoring(lote(12), "--desglose", ruta, "--desglose-append")
            self.assertIs(grande["ok"], False)
            self.assertFalse(os.path.exists(ruta))
            self.assertIs(scoring(lote(5))["ok"], False)
            plan = json.loads(subprocess.run(
                [sys.executable, SCRIPT, "planificar-bloques", "--config", cfg],
                input=json.dumps({"ids": [e["id"] for e in lote(12)["emails"]]}),
                capture_output=True, text=True).stdout)
            self.assertEqual([len(b["ids"]) for b in plan["bloques"]], [6, 6])
            por_id = {e["id"]: e for e in lote(12)["emails"]}
            for b in plan["bloques"]:
                out = scoring({"emails": [por_id[i] for i in b["ids"]]},
                              "--brief", "--desglose", ruta, "--desglose-append")
                self.assertEqual(len(out["resultados"]), 6)
            # El último bloque ve la sesión entera: la plantilla salta.
            self.assertEqual(out["huellas_acumuladas"]["correos_previos"], 6)
            self.assertIn("plantilla_cercana", out["huellas_plantilla"])


class TestValidarConfig(unittest.TestCase):
    def test_avisa_de_valores_raros(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("sin PyYAML")
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "config.yaml")
            cfg = cfg_bloques(activo="si", tam=40)
            with open(ruta, "w") as fh:
                json.dump(cfg, fh)
            avisos = " ".join(th.cmd_validar_config(ruta).get("avisos", []))
            self.assertIn("scoring.bloques", avisos)
            self.assertIn("scoring.tamano_bloque", avisos)
            with open(ruta, "w") as fh:
                json.dump(cfg_bloques(), fh)
            avisos = " ".join(th.cmd_validar_config(ruta).get("avisos", []))
            self.assertNotIn("scoring.bloques", avisos)
            self.assertNotIn("tamano_bloque", avisos)


if __name__ == "__main__":
    unittest.main()
