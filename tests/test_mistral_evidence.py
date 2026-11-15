"""Contrasta las citas de Mistral con el diff enviado, sin red ni API."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.test_mistral_review import HALLAZGO, mr


DIFF = """diff --git a/a.py b/a.py
index 1111111..2222222 100644
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@ def ejecutar():
 contexto = True
-resultado = 1
+resultado = 2
diff --git a/b.py b/b.py
index 3333333..4444444 100644
--- a/b.py
+++ b/b.py
@@ -1 +1 @@
-otro = False
+otro = True
"""


def respuesta(archivo="a.py", fragmento="resultado = 2", **campos):
    hallazgo = dict(HALLAZGO, archivo=archivo, fragmento=fragmento, **campos)
    return json.dumps({"resumen": "Cambio de resultado", "hallazgos": [hallazgo]})


class TestEvidenciaMistral(unittest.TestCase):
    def test_indice_conserva_archivo_y_prefijos_del_hunk(self):
        self.assertEqual(mr.indice_diff(DIFF), {
            "a.py": {" contexto = True", "-resultado = 1", "+resultado = 2"},
            "b.py": {"-otro = False", "+otro = True"},
        })

    def test_admite_citas_con_y_sin_prefijo(self):
        for fragmento in ("resultado = 2", "+resultado = 2", "resultado = 1",
                          "-resultado = 1", "contexto = True", " contexto = True"):
            with self.subTest(fragmento=fragmento):
                self.assertIsNotNone(mr.interpretar(respuesta(fragmento=fragmento), DIFF))

    def test_rechaza_archivos_o_citas_inventados(self):
        for archivo, fragmento in (("inventado.py", "resultado = 2"),
                                  ("a.py", "resultado = 3"),
                                  ("a.py", "otro = True"),
                                  ("a.py", "resultado")):
            with self.subTest(archivo=archivo, fragmento=fragmento):
                self.assertIsNone(mr.interpretar(respuesta(archivo, fragmento), DIFF))

    def test_no_acepta_metadatos_como_evidencia(self):
        for fragmento in ("diff --git a/a.py b/a.py", "index 1111111..2222222 100644",
                          "--- a/a.py", "+++ b/a.py", "@@ -1,2 +1,2 @@ def ejecutar():",
                          "def ejecutar():"):
            with self.subTest(fragmento=fragmento):
                self.assertIsNone(mr.interpretar(respuesta(fragmento=fragmento), DIFF))

    def test_rechaza_cita_multilinea(self):
        self.assertIsNone(mr.interpretar(
            respuesta(fragmento="contexto = True\nresultado = 2"), DIFF))

    def test_acepta_lineas_seguidas_de_un_mismo_hunk(self):
        # Decisión del mantenedor: GLM 5.3 Flash citaba el defecto con sus dos
        # líneas y se perdía la revisión entera.
        for fragmento in ("-resultado = 1\n+resultado = 2",
                          " contexto = True\n-resultado = 1\n+resultado = 2",
                          "contexto = True\n\nresultado = 1",      # en blanco: no cuenta
                          "    resultado = 1  \n  resultado = 2"):  # sangría libre
            with self.subTest(fragmento=fragmento):
                self.assertIsNotNone(mr.interpretar(respuesta(fragmento=fragmento), DIFF))

    def test_rechaza_lineas_sueltas_inventadas_o_sin_contenido(self):
        dos_hunks = ("diff --git a/c.py b/c.py\n--- a/c.py\n+++ b/c.py\n"
                     "@@ -1 +1 @@\n-a = 0\n+a = 1\n@@ -20 +20 @@\n-b = 0\n+b = 1\n")
        casos = ((DIFF, "a.py", "resultado = 2\notro = True"),   # en otro archivo
                 (DIFF, "a.py", "resultado = 2\ncontexto = True"),  # orden invertido
                 (DIFF, "a.py", "resultado = 2\ninventada = 3"),
                 (DIFF, "a.py", "resultado = 2 \\\nmas"),
                 (dos_hunks, "c.py", "a = 1\nb = 0"),             # hunks distintos
                 (dos_hunks, "c.py", ")\n)"))
        for diff, archivo, fragmento in casos:
            with self.subTest(fragmento=fragmento):
                diagnostico = []
                self.assertIsNone(mr.interpretar(
                    respuesta(archivo=archivo, fragmento=fragmento), diff,
                    diagnostico=diagnostico))
                self.assertTrue(diagnostico)

    def test_el_control_tal_como_lo_cito_glm(self):
        diff = ("diff --git a/scripts/d.py b/scripts/d.py\n--- a/scripts/d.py\n"
                "+++ b/scripts/d.py\n@@ -50,2 +50,9 @@ def _nombre_tramo(tramo):\n"
                "     return x\n \n"
                "+def _porcentaje(n, total):\n"
                '+    """Porcentaje de `n` sobre `total`; 0 si no hay correos."""\n'
                "+    if total:\n+        return 0.0\n+    return 100.0 * n / total\n+\n+\n")
        for fragmento in ("+    if total:\n+        return 0.0\n+    return 100.0 * n / total",
                          "    if total:\n        return 0.0"):
            with self.subTest(fragmento=fragmento):
                self.assertIsNotNone(mr.interpretar(
                    respuesta(archivo="scripts/d.py", fragmento=fragmento), diff))

    def test_bloques_por_hunk_y_en_orden(self):
        dos_hunks = ("diff --git a/c.py b/c.py\n--- a/c.py\n+++ b/c.py\n"
                     "@@ -1 +1 @@\n-a = 0\n+a = 1\n@@ -20 +20 @@\n-b = 0\n+b = 1\n")
        self.assertEqual(mr.bloques_diff(dos_hunks), {
            "c.py": [["-a = 0", "+a = 1"], ["-b = 0", "+b = 1"]]})
        self.assertEqual(mr.bloques_diff(DIFF)["a.py"],
                         [[" contexto = True", "-resultado = 1", "+resultado = 2"]])

    def test_cita_en_linea_recortada_no_se_acredita_como_linea_completa(self):
        diff = DIFF[:DIFF.index("+resultado = 2")] + '+resultado = "tex'
        self.assertIsNone(mr.interpretar(
            respuesta(fragmento='resultado = "tex'), diff))
        self.assertIsNotNone(mr.interpretar(
            respuesta(fragmento="contexto = True"), diff))

    def test_un_hallazgo_invalido_no_se_descarta_en_silencio(self):
        datos = json.loads(respuesta())
        datos["hallazgos"].append(dict(HALLAZGO, archivo="no.py"))
        self.assertIsNone(mr.interpretar(json.dumps(datos), DIFF))

    def test_diff_vacio_no_acredita_ningun_hallazgo(self):
        self.assertIsNone(mr.interpretar(respuesta(), ""))
        self.assertEqual(mr.interpretar(
            json.dumps({"resumen": "R", "hallazgos": []}), ""), ("R", []))

    def test_sin_diff_conserva_validacion_de_esquema(self):
        self.assertIsNotNone(mr.interpretar(respuesta()))
        self.assertIsNone(mr.interpretar(respuesta(escenario="")))

    def test_renombrado_se_cita_con_ruta_nueva(self):
        diff = """diff --git a/antes.py b/despues.py
similarity index 80%
rename from antes.py
rename to despues.py
index 1111111..2222222 100644
--- a/antes.py
+++ b/despues.py
@@ -1 +1 @@
-resultado = 1
+resultado = 2
"""
        self.assertIsNotNone(mr.interpretar(respuesta("despues.py"), diff))
        self.assertIsNone(mr.interpretar(respuesta("antes.py"), diff))

    def test_borrado_se_cita_con_ruta_vieja(self):
        diff = """diff --git a/borrado.py b/borrado.py
deleted file mode 100644
index 1111111..0000000
--- a/borrado.py
+++ /dev/null
@@ -1 +0,0 @@
-resultado = 1
"""
        self.assertIsNotNone(mr.interpretar(
            respuesta("borrado.py", "resultado = 1"), diff))
        self.assertNotIn("/dev/null", mr.indice_diff(diff))

    def test_alta_se_cita_con_ruta_nueva(self):
        diff = """diff --git a/nuevo.py b/nuevo.py
new file mode 100644
index 0000000..2222222
--- /dev/null
+++ b/nuevo.py
@@ -0,0 +1 @@
+resultado = 2
"""
        self.assertIsNotNone(mr.interpretar(respuesta("nuevo.py"), diff))

    def test_hunk_con_lineas_que_parecen_cabeceras(self):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
--- texto anterior
+++ texto nuevo
 contexto
"""
        self.assertEqual(mr.indice_diff(diff), {
            "a.py": {"--- texto anterior", "+++ texto nuevo", " contexto"},
        })
        self.assertIsNotNone(mr.interpretar(
            respuesta(fragmento="++ texto nuevo"), diff))

    def test_marcador_sin_salto_de_linea_no_es_evidencia(self):
        diff = DIFF + "\\ No newline at end of file\n"
        self.assertIsNone(mr.interpretar(
            respuesta("b.py", "\\ No newline at end of file"), diff))

    def test_rutas_reales_con_espacios_control_y_utf8_citado_por_git(self):
        rutas = ("con espacio.py", "tab\tnombre.py", "acción.py", "comilla\".py")
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)

            def git(*args):
                return subprocess.run(["git", "-C", temporal, *args], check=True,
                                      capture_output=True, text=True).stdout

            git("init", "-q")
            git("config", "user.email", "prueba@example.invalid")
            git("config", "user.name", "Prueba")
            git("config", "core.quotePath", "true")
            for ruta in rutas:
                (raiz / ruta).write_text("resultado = 1\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "Base de prueba")
            for ruta in rutas:
                (raiz / ruta).write_text("resultado = 2\n", encoding="utf-8")
            diff = git("diff", "--no-ext-diff")

        indice = mr.indice_diff(diff)
        self.assertEqual(set(indice), set(rutas))
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertIsNotNone(mr.interpretar(respuesta(ruta), diff))


if __name__ == "__main__":
    unittest.main()
