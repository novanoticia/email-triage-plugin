"""Ensayo P3 (v3.20, opt-in): capa config-ensayo-p3.yaml sobre config.yaml.

Fija el contrato aprobado por el mantenedor: siguen 30 criterios activos y
13 core; 5, 19 y 26 se desactivan y se sustituyen; la fusión 5+26 cuenta una
sola vez; responsabilidad_personal no abre REPLY_NEEDED; el config.yaml
principal no cambia. Solo stdlib + PyYAML (se omite sin él); sin red.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402  (pone scripts/ en sys.path)
import triage_helpers as th  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

SKILL = os.path.dirname(DIR_SCRIPTS)
RUTA_CFG = os.path.join(SKILL, "config.yaml")
RUTA_CAPA = os.path.join(SKILL, "config-ensayo-p3.yaml")
NUEVOS = ("razonamiento_dirigido", "alternativas_reales", "responsabilidad_personal")
SUSTITUIDOS = ("forward_backward_flow", "fake_justification", "third_alternative")


@unittest.skipIf(yaml is None, "PyYAML no instalado")
class TestCapa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = th._cargar_config(RUTA_CFG)
        cls.cfg = th._fusiona_config_ensayo(cls.base, RUTA_CAPA)
        cls.crit = cls.cfg["criterios_epistemicos"]

    def _activos(self, crit):
        return [k for k, c in crit.items() if c.get("activo", True)]

    def test_siguen_30_activos_y_13_core(self):
        activos = self._activos(self.crit)
        self.assertEqual(len(activos), 30)
        core = [k for k in activos if self.crit[k].get("core") is True]
        self.assertEqual(len(core), 13)

    def test_sustituidos_inactivos_y_nuevos_activos(self):
        for k in SUSTITUIDOS:
            self.assertIs(self.crit[k]["activo"], False, k)
        for k in NUEVOS:
            self.assertIs(self.crit[k]["activo"], True, k)
        self.assertIs(self.crit["razonamiento_dirigido"]["core"], True)
        self.assertIs(self.crit["responsabilidad_personal"]["core"], False)

    def test_todo_activo_tiene_eje_valido(self):
        ejes = self.cfg["scoring"]["ejes"]
        for k in self._activos(self.crit):
            self.assertIn(self.crit[k].get("eje"), ejes, k)

    def test_capa_sin_claves_booleanas(self):
        # Gotcha YAML 1.1: un si:/no: sin comillas se vuelve booleano.
        with open(RUTA_CAPA, encoding="utf-8") as f:
            capa = yaml.safe_load(f)
        for k, c in capa["criterios_epistemicos"].items():
            self.assertTrue(all(isinstance(x, str) for x in c), k)

    def test_baremos_aprobados(self):
        def valores(k):
            return {a: b for a, b in self.crit[k].items()
                    if a not in th._META_CRIT}
        self.assertEqual(valores("razonamiento_dirigido"),
                         {"exploratorio": 3, "justificacion_legitima": 0,
                          "racionalizacion": -3})
        self.assertEqual(valores("alternativas_reales"),
                         {"aporta_alternativa": 3, "binario_honesto": 0,
                          "falso_dilema": -2})
        self.assertEqual(valores("responsabilidad_personal"),
                         {"asignada": 3, "compartida": 1, "solo_informativa": 0})

    def test_el_config_principal_no_cambia(self):
        crit = self.base["criterios_epistemicos"]
        self.assertEqual(len(crit), 30)
        for k in NUEVOS:
            self.assertNotIn(k, crit)
        self.assertIs(self.base["scoring"]["ensayo_p3"], False)


@unittest.skipIf(yaml is None, "PyYAML no instalado")
class TestScoringEnsayo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = th._cargar_config(RUTA_CFG)
        cls.cfg = th._fusiona_config_ensayo(cls.base, RUTA_CAPA)

    def test_la_fusion_5_26_cuenta_una_sola_vez(self):
        antes = th.cmd_scoring({"verdicts": {"forward_backward_flow": "backward",
                                             "fake_justification": "si"}}, self.base)
        despues = th.cmd_scoring({"verdicts": {"razonamiento_dirigido":
                                               "racionalizacion"}}, self.cfg)
        self.assertEqual(antes["ejes_sin_clampar"]["calidad_epistemica"], -5)
        self.assertEqual(despues["ejes_sin_clampar"]["calidad_epistemica"], -3)

    def test_veredicto_a_un_criterio_sustituido_se_ignora(self):
        r = th.cmd_scoring({"verdicts": {"forward_backward_flow": "forward"}},
                           self.cfg)
        self.assertEqual(r["ignorados"][0]["criterio"], "forward_backward_flow")
        self.assertEqual(r["ejes"]["calidad_epistemica"], 0)

    def test_responsabilidad_no_abre_reply_needed(self):
        r = th.cmd_scoring({"verdicts": {"responsabilidad_personal": "asignada"},
                            "extra_points": 20}, self.cfg)
        self.assertNotEqual(r["tier"], "REPLY_NEEDED")
        self.assertEqual(r["ejes"]["presion_accion"], 3)

    def test_falso_dilema_resta_en_valor_decisional(self):
        r = th.cmd_scoring({"verdicts": {"alternativas_reales": "falso_dilema"}},
                           self.cfg)
        self.assertEqual(r["ejes_sin_clampar"]["valor_decisional"], -2)

    def test_sin_capa_no_hay_criterios_nuevos(self):
        r = th.cmd_scoring({"verdicts": {"razonamiento_dirigido": "exploratorio"}},
                           self.base)
        self.assertEqual(r["ignorados"][0]["criterio"], "razonamiento_dirigido")

    def test_cobertura_p2_ve_13_core_con_la_capa(self):
        cfg = th._merge_config(self.cfg, {"scoring": {"contrato_p2": True}})
        r = th.cmd_scoring({"verdicts": {}}, cfg)
        self.assertEqual(r["cobertura"]["core_total"], 13)
        self.assertIn("razonamiento_dirigido", r["cobertura"]["core_sin_explicar"])


@unittest.skipIf(yaml is None, "PyYAML no instalado")
class TestCLI(unittest.TestCase):
    """De punta a punta: el flag --config-ensayo llega al scoring."""

    def _scoring(self, *extra, payload):
        cmd = [sys.executable, os.path.join(DIR_SCRIPTS, "triage_helpers.py"),
               "scoring", "--config", RUTA_CFG, *extra]
        p = subprocess.run(cmd, input=json.dumps(payload), capture_output=True,
                           text=True, timeout=60)
        return json.loads(p.stdout)

    def test_con_capa(self):
        r = self._scoring("--config-ensayo", RUTA_CAPA, payload={
            "verdicts": {"razonamiento_dirigido": "exploratorio"}})
        self.assertEqual(r["ejes"]["calidad_epistemica"], 3)

    def test_ruta_inexistente_es_no_op(self):
        r = self._scoring("--config-ensayo", "/no/existe.yaml", payload={
            "verdicts": {"razonamiento_dirigido": "exploratorio"}})
        self.assertEqual(r["ejes"]["calidad_epistemica"], 0)

    def test_capa_rota_da_error_legible(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "rota.yaml")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write("criterios_epistemicos: [\n")
            r = self._scoring("--config-ensayo", ruta, payload={"verdicts": {}})
        # Mismo contrato que la capa veloz: error legible con línea, sin
        # traceback (el texto lo pone el parser YAML vía _payload_error_yaml).
        self.assertIs(r["ok"], False)
        self.assertIn("linea", r)


@unittest.skipIf(yaml is None, "PyYAML no instalado")
class TestValidarConfig(unittest.TestCase):
    def test_aviso_si_no_es_booleano(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "config.yaml")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write('scoring:\n  ensayo_p3: "si"\n')
            r = th.cmd_validar_config(ruta)
        self.assertTrue(any("ensayo_p3" in a for a in r.get("avisos", [])), r)


class TestDocumentacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "references", "ensayo-p3.md"),
                  encoding="utf-8") as f:
            cls.ref = f.read()
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            cls.skill = f.read()

    def test_la_referencia_nombra_los_seis_criterios(self):
        for k in NUEVOS + SUSTITUIDOS:
            self.assertIn("`%s`" % k, self.ref, k)

    def test_stub_del_skill_con_condicion_de_entrada(self):
        i = self.skill.index("**Ensayo P3 (opt-in):**")
        stub = self.skill[i:i + 400]
        self.assertIn("references/ensayo-p3.md", stub)
        self.assertIn("scoring.ensayo_p3: true", stub)
        self.assertIn("--config-ensayo", stub)


if __name__ == "__main__":
    unittest.main()
