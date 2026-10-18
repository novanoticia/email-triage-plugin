"""diagnostico-ejes (ROADMAP P1, Fase 1): mide la saturación sin cambiar nada.

Fija: los recuentos de saturación y puntos perdidos, la detección de tiers
que cambiarían sin recorte, el peso de reglas duras + extras, que acepta lote
y resultados sueltos, que es una función TOTAL y que el comando de punta a
punta lee lo que escribe `scoring --desglose`. Solo stdlib (+ PyYAML en el
CLI); sin red; las escrituras van a tempfiles.
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402  (pone scripts/ en sys.path)
import triage_helpers as th  # noqa: E402

TIERS = {"reply_needed": 10, "review": 4, "reading_later": 0}
SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")
CFG = os.path.join(os.path.dirname(DIR_SCRIPTS), "config.yaml")


def _res(ejes, crudos, score, id_=None):
    r = {"ejes": ejes, "ejes_sin_clampar": crudos, "score": score}
    if id_ is not None:
        r["id"] = id_
    return r


class TestRecuentos(unittest.TestCase):
    def test_saturacion_y_puntos_perdidos(self):
        docs = [{"resultados": [
            _res({"vd": 10, "ce": -10}, {"vd": 13, "ce": -12}, 0, 1),
            _res({"vd": 4, "ce": 2}, {"vd": 4, "ce": 2}, 6, 2),
        ]}]
        r = th.cmd_diagnostico_ejes(docs, {"tiers": TIERS})
        self.assertEqual(r["correos"], 2)
        self.assertEqual(r["por_eje"]["vd"]["saturado_arriba"], 1)
        self.assertEqual(r["por_eje"]["vd"]["puntos_perdidos"], 3)
        self.assertEqual(r["por_eje"]["ce"]["saturado_abajo"], 1)
        self.assertEqual(r["por_eje"]["vd"]["pct_saturado"], 50.0)

    def test_tier_que_cambiaria_sin_recorte(self):
        # 10 + 1 extra = score 11 (REPLY por umbral); sin recorte 8+... baja
        r = th.cmd_diagnostico_ejes(
            [_res({"vd": 8}, {"vd": 11}, 8, "x")], {"tiers": TIERS})
        self.assertEqual(r["cambiarian_tier_sin_recorte"], 1)
        c = r["detalle_cambios"][0]
        self.assertEqual((c["tier"], c["tier_sin_recorte"]),
                         ("REVIEW", "REPLY_NEEDED"))

    def test_peso_y_decision_de_los_extras(self):
        # ejes suman 2 (READING_LATER); +4 de extras lo llevan a REVIEW.
        r = th.cmd_diagnostico_ejes([_res({"vd": 2}, {"vd": 2}, 6)],
                                    {"tiers": TIERS})
        self.assertEqual(r["tier_decidido_por_extras"], 1)
        self.assertEqual(r["peso_medio_extras_pct"], round(100 * 4 / 6, 1))

    def test_sin_saturacion_ni_cambios(self):
        r = th.cmd_diagnostico_ejes([_res({"vd": 3}, {"vd": 3}, 3)],
                                    {"tiers": TIERS})
        self.assertEqual(r["por_eje"]["vd"]["pct_saturado"], 0.0)
        self.assertEqual(r["cambiarian_tier_sin_recorte"], 0)

    def test_basura_va_a_ignorados(self):
        r = th.cmd_diagnostico_ejes([5, {"score": 1}, _res({"vd": 1}, {"vd": 1}, 1)],
                                    {"tiers": TIERS})
        self.assertEqual(r["correos"], 1)
        self.assertEqual(len(r["ignorados"]), 2)

    def test_no_lista_da_error_legible(self):
        r = th.cmd_diagnostico_ejes({"resultados": []}, {})
        self.assertIs(r["ok"], False)


class TestTotalidad(unittest.TestCase):
    def test_es_total(self):
        from tests.test_triage_helpers import _rand_json
        rng = random.Random(20261018)
        for _ in range(2000):
            r = th.cmd_diagnostico_ejes(_rand_json(rng), _rand_json(rng))
            self.assertIsInstance(r, dict)
            json.dumps(r, ensure_ascii=False)


class TestCLI(unittest.TestCase):
    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML no instalado")

    def test_lee_lo_que_escribe_scoring_desglose(self):
        lote = {"emails": [
            {"id": 1, "verdicts": {"cambia_algo_concreto": "si",
                                   "cambio_predicciones": "si",
                                   "hug_the_query": "directo"}},
            {"id": 2, "verdicts": {"cambia_algo_concreto": "no"}},
        ]}
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "desgloses", "s1.json")
            subprocess.run([sys.executable, SCRIPT, "scoring", "--config", CFG,
                            "--brief", "--desglose", ruta],
                           input=json.dumps(lote), capture_output=True,
                           text=True, check=True, timeout=60)
            p = subprocess.run([sys.executable, SCRIPT, "diagnostico-ejes",
                                "--desglose", ruta, os.path.join(d, "no.json"),
                                "--config", CFG],
                               capture_output=True, text=True, timeout=60)
        r = json.loads(p.stdout)
        self.assertIs(r["ok"], True)
        self.assertEqual(r["correos"], 2)
        # Correo 1: 5 + 4 + 4 = 13, recortado a 10 (pierde 3). Correo 2:
        # -5, recortado a 0 (pierde 5). Total 8.
        self.assertEqual(r["por_eje"]["valor_decisional"]["puntos_perdidos"], 8)
        self.assertEqual(r["por_eje"]["valor_decisional"]["saturado_arriba"], 1)
        self.assertEqual(r["por_eje"]["valor_decisional"]["saturado_abajo"], 1)
        self.assertEqual(r["ignorados"][0]["ruta"], os.path.join(d, "no.json"))


class TestDocumentacion(unittest.TestCase):
    def test_plantilla_lo_trae_apagado(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML no instalado")
        with open(CFG, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.assertIs(cfg["telemetria"]["guardar_desglose"], False)

    def test_el_skill_lo_instruye(self):
        with open(os.path.join(os.path.dirname(DIR_SCRIPTS), "SKILL.md"),
                  encoding="utf-8") as f:
            skill = f.read()
        self.assertIn("telemetria.guardar_desglose: true", skill)
        self.assertIn("diagnostico-ejes", skill)


if __name__ == "__main__":
    unittest.main()
