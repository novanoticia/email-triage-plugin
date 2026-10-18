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


def _cli_scoring(ruta, lote, *extra):
    return subprocess.run([sys.executable, SCRIPT, "scoring", "--config", CFG,
                           "--brief", *extra, "--desglose", ruta],
                          input=json.dumps(lote), capture_output=True,
                          text=True, check=True, timeout=60)


class TestDesgloseAcumulado(unittest.TestCase):
    """v3.21.5: `--desglose-append` añade una línea por invocación en vez de
    sobrescribir. La sobrescritura borraba la primera pasada cuando el modelo
    veía el lote y retocaba veredictos; ahora diagnostico-ejes lo detecta y
    cuenta cada correo una sola vez (su última pasada)."""

    LOTE1 = {"emails": [
        {"id": 1, "verdicts": {"cambia_algo_concreto": "si"}},
        {"id": 2, "verdicts": {"cambia_algo_concreto": "no"}},
    ]}
    LOTE2 = {"emails": [
        {"id": 1, "verdicts": {"cambia_algo_concreto": "si",
                               "cambio_predicciones": "si"}},
    ]}

    def test_dos_pasadas_un_repuntuado(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "desgloses", "s1.jsonl")
            a = _cli_scoring(ruta, self.LOTE1, "--desglose-append")
            _cli_scoring(ruta, self.LOTE2, "--desglose-append")
            with open(ruta, encoding="utf-8") as f:
                lineas = f.read().splitlines()
            p = subprocess.run([sys.executable, SCRIPT, "diagnostico-ejes",
                                "--desglose", ruta, "--config", CFG],
                               capture_output=True, text=True, timeout=60)
        self.assertNotIn("desglose_error", json.loads(a.stdout))
        self.assertEqual(len(lineas), 2)
        self.assertEqual(set(json.loads(lineas[0])), {"ts", "desglose"})
        r = json.loads(p.stdout)
        self.assertIs(r["ok"], True)
        self.assertEqual(r["correos"], 2)          # no 3: el id 1 cuenta una vez
        self.assertEqual(r["repuntuados"], 1)
        rep = r["detalle_repuntuados"][0]
        self.assertEqual((rep["id"], rep["pasadas"]), (1, 2))
        self.assertEqual(rep["veredictos_cambiados"], ["cambio_predicciones"])
        self.assertLess(rep["score_antes"], rep["score_despues"])

    def test_sin_el_flag_sigue_sobrescribiendo(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "s1.json")
            _cli_scoring(ruta, self.LOTE1)
            _cli_scoring(ruta, self.LOTE2)
            with open(ruta, encoding="utf-8") as f:
                doc = json.load(f)
        self.assertEqual([x["id"] for x in doc["resultados"]], [1])

    def test_append_sin_ruta_avisa_y_no_escribe(self):
        p = subprocess.run([sys.executable, SCRIPT, "scoring", "--config", CFG,
                            "--brief", "--desglose-append"],
                           input=json.dumps(self.LOTE1), capture_output=True,
                           text=True, check=True, timeout=60)
        out = json.loads(p.stdout)
        self.assertIn("--desglose", out["desglose_error"])
        self.assertEqual(len(out["resultados"]), 2)

    def test_parsear_jsonl_de_una_linea_y_lineas_malas(self):
        una = json.dumps({"ts": "t", "desglose": _res({"vd": 1}, {"vd": 1}, 1, 7)})
        self.assertEqual(th._parsear_desglose(una)["pasadas"][0]["id"], 7)
        doc = th._parsear_desglose(una + "\nbasura\n\n" + una)
        self.assertEqual((len(doc["pasadas"]), doc["lineas_ignoradas"]), (2, [2]))
        with self.assertRaises(ValueError):
            th._parsear_desglose("basura\n{]")
        # El formato de siempre (JSON sobrescrito) no cambia.
        self.assertEqual(th._parsear_desglose('{"resultados": []}'),
                         {"resultados": []})

    def test_pasadas_sin_id_cuentan_todas(self):
        r = th.cmd_diagnostico_ejes(
            [{"pasadas": [_res({"vd": 1}, {"vd": 1}, 1),
                          {"resultados": [_res({"vd": 2}, {"vd": 2}, 2),
                                          _res({"vd": 3}, {"vd": 3}, 3, {"x": 1})]}],
              "lineas_ignoradas": [4]}], {"tiers": TIERS})
        self.assertEqual((r["correos"], r["repuntuados"]), (3, 0))
        self.assertEqual(r["ignorados"][0]["linea"], 4)

    def test_pasadas_basura_no_revienta(self):
        rnd = random.Random(5)
        trozos = [None, 1, "x", [], {}, {"id": 1}, {"resultados": "no"},
                  _res({"vd": 1}, {"vd": 2}, 1, 1), {"id": [1]}]
        for _ in range(300):
            pas = [rnd.choice(trozos) for _ in range(rnd.randint(0, 5))]
            r = th.cmd_diagnostico_ejes([{"pasadas": pas}], {"tiers": TIERS})
            json.dumps(r)
            self.assertIs(r["ok"], True)


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
        self.assertIn("--desglose-append", skill)

    def test_claude_md_lo_anota_en_el_inventario(self):
        with open(os.path.join(_RAIZ, "CLAUDE.md"), encoding="utf-8") as f:
            self.assertIn("--desglose-append", f.read())
        self.assertIn("--desglose-append", th.__doc__)


if __name__ == "__main__":
    unittest.main()
