"""La aclaración sobre S0 y el estado de las traducciones están donde deben."""
import os
import re
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join("plugins", "email-triage", "skills", "email-triage")


def leer(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


def plano(rel):
    """Texto con espacios normalizados: el Markdown se reflujea en varias líneas."""
    return " ".join(leer(rel).split())


def seccion_h2(rel, titulo):
    """Texto (espacios normalizados) de una sección `## titulo` hasta la siguiente `## `."""
    m = re.search(r"(?ms)^## %s\n(.*?)(?=^## )" % re.escape(titulo), leer(rel))
    return " ".join(m.group(1).split()) if m else None


class TestAclaracionS0(unittest.TestCase):
    SITIOS = ["README.md", "CLAUDE.md", "AGENTS.md",
              os.path.join(SKILL, "i18n", "README.md"),
              os.path.join(SKILL, "SKILL.md")]

    def test_cada_sitio_dice_que_s0_cubre_solo_es_en(self):
        for rel in self.SITIOS:
            with self.subTest(rel=rel):
                self.assertIn("solo español e inglés", plano(rel))

    def test_cada_sitio_dice_que_no_cambia_con_idioma(self):
        for rel in ("README.md", "CLAUDE.md", "AGENTS.md"):
            with self.subTest(rel=rel):
                self.assertIn("no cambia con `idioma=`", plano(rel))

    def test_el_readme_distingue_idioma_del_correo_e_idioma_de_la_interfaz(self):
        t = plano("README.md")
        self.assertIn("idioma del correo recibido", t)

    def test_la_aclaracion_esta_en_la_seccion_language_langue_y_no_solo_en_otro_sitio(self):
        """El README la repite (changelog): hay que exigirla DONDE la lee quien elige idioma."""
        sec = seccion_h2("README.md", "Language / Langue")
        self.assertIsNotNone(sec)
        for s in ("solo español e inglés", "no cambia con `idioma=`", "idioma del correo recibido"):
            self.assertIn(s, sec)

    def test_el_changelog_no_se_adelanta_a_la_version(self):
        # Task 12 sube la versión y añade «## Novedades en v3.14.0»; hasta entonces
        # la primera sección de novedades debe seguir siendo la de la versión vigente.
        m = re.search(r"(?m)^## Novedades en v([0-9.]+)", leer("README.md"))
        self.assertIsNotNone(m)


class TestReadme(unittest.TestCase):
    def setUp(self):
        self.t = plano("README.md")

    def test_seccion_language_langue_en_los_tres_idiomas(self):
        self.assertIn("## Language / Langue", leer("README.md"))
        for s in ("idioma=en", "idioma=fr", "AI-generated", "générée par une IA",
                  "generada por una IA"):
            self.assertIn(s, self.t)

    def test_la_seccion_va_antes_del_changelog(self):
        r = leer("README.md")
        self.assertLess(r.index("## Language / Langue"), r.index("## Novedades en v"))

    def test_declara_lo_que_no_se_traduce_y_el_texto_libre(self):
        for s in ("texto libre", "no está revisado", "tiers"):
            self.assertIn(s, self.t)

    def test_afirmacion_de_estado_presente_y_vigilada(self):
        self.assertIn("ninguna traducción está revisada", self.t.lower())

    def test_explica_como_elegir_y_como_anadir_un_idioma(self):
        for s in ("`usuario.idioma`", "i18n/README.md", "no cuenta"):
            self.assertIn(s, self.t)


class TestReglasParaAgentes(unittest.TestCase):
    def test_claude_md_recoge_las_reglas_nuevas(self):
        t = plano("CLAUDE.md")
        for s in ("i18n:inicio", "No escribas literales visibles nuevos fuera del catálogo",
                  "python3 scripts/i18n_validar.py", "python3 scripts/i18n_extraer.py generar",
                  "`triage_helpers.py` no se toca", "riesgo: alto",
                  "`SKILL.md` dice «13 core»"):
            self.assertIn(s, t)

    def test_agents_md_enlaza_a_claude_md_y_resume(self):
        t = plano("AGENTS.md")
        self.assertIn("CLAUDE.md", t)
        self.assertIn("i18n", t)
        self.assertIn("python3 scripts/i18n_validar.py", t)

    def test_agents_no_contradice_a_claude_md_sobre_la_version(self):
        # el bump sigue siendo solo por script; las reglas i18n no lo cambian
        self.assertIn("bump-version.sh", plano("AGENTS.md"))


if __name__ == "__main__":
    unittest.main()
