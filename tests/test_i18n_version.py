"""Versión 3.14.0 y su entrada del changelog: las cifras citadas no pueden desfasarse."""
import json
import os
import re
import unittest

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage")
VERSION = "3.14.0"  # Changelog histórico de i18n.


def leer(*partes):
    with open(os.path.join(RAIZ, *partes), encoding="utf-8") as f:
        return f.read()


VERSION_ACTUAL = json.loads(leer(".claude-plugin", "plugin.json"))["version"]


def seccion_novedades(readme, version):
    m = re.search(r"(?ms)^## Novedades en v%s\n(.*?)(?=^## Novedades en v)" % re.escape(version), readme)
    return " ".join(m.group(1).split()) if m else None


class TestVersion(unittest.TestCase):
    def test_los_nueve_sitios_estan_en_la_version(self):
        j = lambda p: json.loads(leer(*p.split("/")))["version"]
        self.assertEqual(j(".claude-plugin/plugin.json"), VERSION_ACTUAL)
        self.assertEqual(j("plugins/email-triage/.claude-plugin/plugin.json"), VERSION_ACTUAL)
        self.assertEqual(j("plugins/email-triage/plugin.json"), VERSION_ACTUAL)
        self.assertIn(f'"version": "{VERSION_ACTUAL}"', leer(".claude-plugin", "marketplace.json"))
        skill = leer("plugins", "email-triage", "skills", "email-triage", "SKILL.md")
        self.assertIn(f'  version: "{VERSION_ACTUAL}"', skill)
        self.assertRegex(leer("README.md"), r"(?m)^# Email Triage Plugin v%s$" % re.escape(VERSION_ACTUAL))
        self.assertIn(f"plugin email-triage (v{VERSION_ACTUAL})",
                      leer("plugins", "email-triage", "skills", "email-triage", "scripts", "triage_helpers.py"))
        self.assertIn("EMAIL TRIAGE v3.14", leer("plugins", "email-triage", "skills", "email-triage", "config.yaml"))
        self.assertRegex(skill, r"(?m)^# Email Triage v3\.14 —")


class TestChangelog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = leer("README.md")
        cls.sec = seccion_novedades(cls.readme, VERSION)

    def test_la_seccion_historica_existe_y_la_actual_es_la_primera(self):
        self.assertIsNotNone(self.sec)
        primera = re.search(r"(?m)^## Novedades en v([0-9.]+)", self.readme).group(1)
        self.assertEqual(primera, VERSION_ACTUAL)

    def test_tiene_anadido_cambiado_y_limitaciones(self):
        for s in ("### Añadido", "### Cambiado", "### Limitaciones"):
            self.assertIn(s, self.sec)

    def test_las_cifras_citadas_coinciden_con_la_realidad(self):
        frases = yaml.safe_load(leer("plugins", "email-triage", "skills", "email-triage", "i18n", "es.yaml"))["frases"]
        self.assertIn(f"{len(frases)} frases", self.sec)
        orig = sum(1 for d in frases.values() if d["origen"] == "original")
        self.assertIn(f"{orig} del original", self.sec)
        # Cifra histórica: el changelog de v3.14.0 describe el bloque de ESA versión
        # (72 líneas). El bloque actual puede crecer (auditoría 2026-10-08, QW4: atajo
        # sin script y entrada por fichero), así que se fija la cifra, no el árbol.
        self.assertIn("72 líneas", self.sec)

    def test_dice_lo_que_cambia_para_quien_ya_tenia_usuario_idioma(self):
        self.assertIn("`usuario.idioma`", self.sec)
        self.assertIn("antes se ignoraba", self.sec)

    def test_limitaciones_honestas(self):
        for s in ("solo español e inglés", "no cambia con `idioma=`", "texto libre",
                  "ninguna traducción está revisada", "plataforma real", "reinstalar"):
            self.assertIn(s, self.sec)

    def test_no_dice_verificado_de_lo_simulado(self):
        self.assertNotRegex(self.sec.lower(), r"\bverificad[oa]s? en (la )?plataforma")

    def test_declara_las_lineas_originales_modificadas(self):
        self.assertIn("líneas del original", self.sec.lower())


if __name__ == "__main__":
    unittest.main()
