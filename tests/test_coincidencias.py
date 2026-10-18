"""coincidencias (v3.21.8): filtros del config calculados por el script.

Fija los fallos reales de las pruebas 6-8 (2026-10-18): direcciones con
+sufijo que no casaban, «RECURSOS» que activaba «curso» y «agentes» como
falso positivo. Y una decisión de seguridad: nunca casar por nombre visible.
Solo stdlib (+ PyYAML en el CLI); sin red; sin escrituras.
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
from tests import DIR_SCRIPTS  # noqa: E402
import triage_helpers as th  # noqa: E402

SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")
CFG = {"filtros": {
    "remitentes_prioritarios": ["sociologiainquieta@substack.com",
                                "zizek@substack.com", "@cienciacognitiva.org",
                                "Slavoj Žižek"],
    "remitentes_ignorar": ["spam@ofertas.com"],
    "palabras_clave_boost": [{"palabra": "Psicología", "peso": "alto"},
                             {"palabra": "Claude Code", "peso": "medio"},
                             "agentes"],
    "palabras_clave_penalizar": ["curso"]}}


def _uno(remitente, asunto="", cuerpo=""):
    r = th.cmd_coincidencias({"correos": [{"id": 1, "remitente": remitente,
                                           "asunto": asunto, "cuerpo": cuerpo}]},
                             CFG)
    return r, r["resultados"][0]


class TestRemitentes(unittest.TestCase):
    def test_sufijo_mas_se_ignora(self):
        _, r = _uno("Sociología Inquieta "
                    "<sociologiainquieta+sociologia-y-cine@substack.com>")
        self.assertTrue(r["prioritario"])
        self.assertEqual(r["extra_points_filtros"], 3)

    def test_otra_direccion_del_mismo_dominio_no_casa(self):
        # zizek@ en el config, slavoj@ en la realidad: no es el mismo buzón.
        out, r = _uno("Slavoj Žižek <slavoj+politics@substack.com>")
        self.assertFalse(r["prioritario"])
        self.assertIn("zizek@substack.com", out["prioritarios_sin_coincidencia"])

    def test_nunca_por_nombre_visible(self):
        out, r = _uno("Slavoj Žižek <phishing@malo.example>")
        self.assertFalse(r["prioritario"])
        self.assertIn("Slavoj Žižek", out["entradas_no_validas"])

    def test_direccion_dentro_del_nombre_entre_comillas_no_cuenta(self):
        # Codex (PR 77): «"Trusted <boss@x>" <atacante@y>» no es de boss@x.
        _, r = _uno('"Socio <sociologiainquieta@substack.com>" <atacante@malo.example>')
        self.assertFalse(r["prioritario"])
        _, r = _uno('"Atacante <atacante@malo.example>" <sociologiainquieta@substack.com>')
        self.assertTrue(r["prioritario"])

    def test_tildes_en_el_buzon_si_cuentan(self):
        # Codex (PR 77): josé@ y jose@ son buzones distintos.
        cfg = {"filtros": {"remitentes_ignorar": ["josé@example.com"]}}
        uno = lambda rem: th.cmd_coincidencias(
            {"correos": [{"remitente": rem}]}, cfg)["resultados"][0]["ignorar"]
        self.assertTrue(uno("José <JOSÉ@example.com>"))
        self.assertFalse(uno("jose@example.com"))

    def test_dominio_y_subdominio(self):
        self.assertTrue(_uno("x@cienciacognitiva.org")[1]["prioritario"])
        self.assertTrue(_uno("Boletín <a@news.cienciacognitiva.org>")[1]["prioritario"])
        self.assertFalse(_uno("a@nocienciacognitiva.org")[1]["prioritario"])

    def test_mayusculas_y_ignorar(self):
        _, r = _uno("SPAM@Ofertas.COM")
        self.assertTrue(r["ignorar"])
        self.assertFalse(r["prioritario"])


class TestPalabrasClave(unittest.TestCase):
    def test_recursos_no_es_curso(self):
        _, r = _uno("val@polymatas.com", "PdS: RECURSOS de la semana")
        self.assertEqual(r["extra_points_filtros"], 0)
        _, r = _uno("val@polymatas.com", "Abre el Curso avanzado")
        self.assertEqual(r["extra_points_filtros"], -2)

    def test_agente_no_es_agentes(self):
        _, r = _uno("a@b.com", "Un agente doble", "el agente")
        self.assertEqual(r["detalle"], [])

    def test_pesos_tildes_y_cuerpo(self):
        _, r = _uno("a@b.com", "Nueva psicologia social")
        self.assertEqual(r["extra_points_filtros"], 3)
        _, r = _uno("a@b.com", "Novedades", "This week in claude code")
        self.assertEqual(r["extra_points_filtros"], 1)    # solo en cuerpo: +1
        _, r = _uno("a@b.com", "Agentes y Claude Code")
        self.assertEqual(r["extra_points_filtros"], 1 + 2)

    def test_no_devuelve_texto_del_correo(self):
        out, _ = _uno("a@b.com", "SECRETO-123 psicología", "CUERPO-XYZ")
        self.assertNotIn("SECRETO-123", json.dumps(out, ensure_ascii=False))
        self.assertNotIn("CUERPO-XYZ", json.dumps(out, ensure_ascii=False))


class TestTotalidad(unittest.TestCase):
    def test_entradas_raras_no_revientan(self):
        rnd = random.Random(7)
        trozos = [None, 1, "x", [], {}, {"id": 1}, {"remitente": 3},
                  {"remitente": "<@>", "asunto": None},
                  {"remitente": "a@b", "asunto": "(?=", "cuerpo": "\\"}]
        cfgs = [CFG, {}, None, {"filtros": {"palabras_clave_boost": [3, {"palabra": 2}],
                                            "remitentes_prioritarios": "x"}}]
        for _ in range(400):
            datos = rnd.choice([None, [], {"correos": "no"},
                                {"correos": [rnd.choice(trozos) for _ in range(3)]}])
            r = th.cmd_coincidencias(datos, rnd.choice(cfgs))
            json.dumps(r)
            self.assertIn("ok", r)

    def test_cli_de_punta_a_punta(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML no instalado")
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "config.yaml")
            with open(ruta, "w", encoding="utf-8") as f:
                yaml.safe_dump(CFG, f, allow_unicode=True)
            p = subprocess.run([sys.executable, SCRIPT, "coincidencias",
                                "--config", ruta],
                               input=json.dumps({"correos": [{"id": 7,
                                   "remitente": "a+x@cienciacognitiva.org",
                                   "asunto": "Psicología"}]}),
                               capture_output=True, text=True, timeout=60)
        r = json.loads(p.stdout)
        self.assertEqual(r["resultados"][0]["extra_points_filtros"], 6)


class TestDocumentacion(unittest.TestCase):
    def test_skill_y_referencia_lo_instruyen(self):
        base = os.path.dirname(DIR_SCRIPTS)
        with open(os.path.join(base, "SKILL.md"), encoding="utf-8") as f:
            self.assertIn("coincidencias", f.read())
        with open(os.path.join(base, "references", "personalizacion.md"),
                  encoding="utf-8") as f:
            self.assertIn("Nunca por nombre visible", f.read())


if __name__ == "__main__":
    unittest.main()
