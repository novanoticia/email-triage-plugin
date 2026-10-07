"""Qué viaja en la carpeta de la skill (lo que el cliente empaqueta) y el job i18n del CI."""
import os
import re
import unittest

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage")
WORKFLOW = os.path.join(RAIZ, ".github", "workflows", "tests.yml")


def ficheros(base):
    for d, _, fs in os.walk(base):
        for f in fs:
            yield os.path.relpath(os.path.join(d, f), base).replace(os.sep, "/")


class TestPaquete(unittest.TestCase):
    """No hay script de empaquetado: el cliente empaqueta la carpeta de la skill entera."""

    def setUp(self):
        self.f = set(ficheros(SKILL))

    def test_incluye_catalogos_y_resolver(self):
        for r in ("i18n/es.yaml", "i18n/en.yaml", "i18n/fr.yaml", "i18n/glosario.yaml",
                  "i18n/README.md", "scripts/idioma.py"):
            self.assertIn(r, self.f)

    def test_no_incluye_herramientas_de_desarrollo_ni_tests(self):
        malos = [r for r in self.f if r.startswith("tests/") or "/test_" in "/" + r
                 or os.path.basename(r).startswith("i18n_")]
        self.assertEqual(malos, [])

    def test_las_herramientas_viven_en_scripts_de_la_raiz(self):
        for r in ("i18n_baseline.py", "i18n_extraer.py", "i18n_validar.py", "i18n_fuentes.yaml",
                  "i18n_mutar.py"):
            self.assertTrue(os.path.exists(os.path.join(RAIZ, "scripts", r)), r)

    def test_los_catalogos_no_son_vacios_ni_symlinks(self):
        for cod in ("es", "en", "fr"):
            p = os.path.join(SKILL, "i18n", cod + ".yaml")
            self.assertFalse(os.path.islink(p))
            self.assertGreater(os.path.getsize(p), 1000)

    def test_ningun_catalogo_ni_script_i18n_escapa_de_la_carpeta(self):
        for r in self.f:
            self.assertFalse(os.path.islink(os.path.join(SKILL, r)), r)

    def test_solo_los_ficheros_i18n_esperados(self):
        i18n = sorted(r for r in self.f if r.startswith("i18n/"))
        self.assertEqual(i18n, ["i18n/README.md", "i18n/en.yaml", "i18n/es.yaml",
                                "i18n/fr.yaml", "i18n/glosario.yaml"])


class TestWorkflowI18n(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WORKFLOW, encoding="utf-8") as f:
            cls.wf = yaml.safe_load(f)
        cls.job = cls.wf["jobs"].get("i18n")

    def test_los_jobs_existentes_siguen_y_hay_uno_nuevo_llamado_i18n(self):
        self.assertEqual(set(self.wf["jobs"]), {"unittest", "sincronia-con-release", "i18n"})

    def test_el_nombre_exacto_del_check_es_el_id_del_job(self):
        # sin `name:` propio, el check se llama como el id del job
        self.assertNotIn("name", self.job)

    def test_permisos_de_solo_lectura(self):
        self.assertEqual(self.job.get("permissions"), {"contents": "read"})

    def test_pasos_esperados(self):
        cmds = "\n".join(s.get("run", "") for s in self.job["steps"])
        usos = [s.get("uses", "") for s in self.job["steps"]]
        self.assertTrue(any(u.startswith("actions/checkout@") for u in usos))
        self.assertTrue(any(u.startswith("actions/setup-python@") for u in usos))
        self.assertIn("-r requirements.txt", cmds)
        self.assertIn("python3 scripts/i18n_validar.py", cmds)
        self.assertIn("python3 scripts/i18n_extraer.py generar", cmds)
        self.assertIn("git diff --exit-code -- plugins/email-triage/skills/email-triage/i18n/es.yaml", cmds)
        self.assertIn("-p \"test_i18n*.py\"", cmds)
        self.assertIn("tests.test_idioma", cmds)

    def test_el_orden_es_extraer_y_luego_comparar(self):
        cmds = "\n".join(s.get("run", "") for s in self.job["steps"])
        self.assertLess(cmds.index("i18n_extraer.py generar"), cmds.index("git diff --exit-code"))

    def test_las_pruebas_que_nombra_el_job_existen(self):
        cmds = "\n".join(s.get("run", "") for s in self.job["steps"])
        for m in re.findall(r"tests\.(test_\w+)", cmds):
            self.assertTrue(os.path.exists(os.path.join(RAIZ, "tests", m + ".py")), m)
        self.assertTrue(any(f.startswith("test_i18n") for f in os.listdir(os.path.join(RAIZ, "tests"))))

    def test_el_job_principal_instala_pyyaml_desde_requirements(self):
        cmds = "\n".join(s.get("run", "") for s in self.wf["jobs"]["unittest"]["steps"])
        self.assertIn("-r requirements.txt", cmds)


if __name__ == "__main__":
    unittest.main()
