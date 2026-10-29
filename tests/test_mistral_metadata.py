"""Comprobaciones de cambios sin hunks con diffs generados por Git real."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.test_mistral_review import COMPROBACION, HALLAZGO, mr


class TestMetadatosMistral(unittest.TestCase):
    @contextmanager
    def repositorio(self):
        with tempfile.TemporaryDirectory() as temporal:
            anterior = os.getcwd()
            os.chdir(temporal)
            try:
                self.git("init", "-q")
                self.git("config", "user.email", "prueba@example.invalid")
                self.git("config", "user.name", "Prueba")
                self.git("config", "core.filemode", "true")
                yield Path(temporal)
            finally:
                os.chdir(anterior)

    def git(self, *args):
        return subprocess.run(["git", *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "Cambio de prueba")
        return self.git("rev-parse", "HEAD")

    def comprobar(self, base, cabeza, ruta):
        diff = mr.obtener_diff(base, cabeza)
        rutas = mr.obtener_rutas_diff(base, cabeza)
        self.assertTrue(diff)
        self.assertNotIn("@@ ", diff)
        self.assertEqual(mr.indice_diff(diff), {})
        self.assertEqual(rutas, {ruta})
        datos = {"resumen": "Cambio sin líneas de código",
                 "hallazgos": [], "comprobaciones": [dict(COMPROBACION, archivo=ruta)]}
        self.assertIsNotNone(mr.interpretar(json.dumps(datos), diff, True, rutas))
        datos["comprobaciones"][0]["archivo"] = "inventado.py"
        self.assertIsNone(mr.interpretar(json.dumps(datos), diff, True, rutas))
        # El inventario permite describir el cambio, nunca citar líneas inexistentes.
        datos["comprobaciones"][0]["archivo"] = ruta
        datos["hallazgos"] = [dict(HALLAZGO, archivo=ruta)]
        self.assertIsNone(mr.interpretar(json.dumps(datos), diff, True, rutas))
        return diff

    def test_renombrado_puro_con_espacios_tab_utf8_y_salto_en_ruta(self):
        with self.repositorio() as raiz:
            vieja = "antes.py"
            nueva = "acción con espacio\ty salto\n.py"
            (raiz / vieja).write_text("resultado = 1\n", encoding="utf-8")
            base = self.commit()
            self.git("mv", vieja, nueva)
            cabeza = self.commit()
            diff = self.comprobar(base, cabeza, nueva)
            self.assertIn("similarity index 100%", diff)

            # Recorrido real de main: el inventario de Git llega al validador.
            evento = raiz / "evento.json"
            evento.write_text(json.dumps({"pull_request": {"number": 7,
                "base": {"sha": base}, "head": {"sha": cabeza}}}), encoding="utf-8")
            respuesta = json.dumps({"resumen": "Renombra el archivo",
                "hallazgos": [], "comprobaciones": [dict(COMPROBACION, archivo=nueva)]})
            with mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "simulada",
                    "GITHUB_EVENT_PATH": str(evento), "GITHUB_REPOSITORY": "o/r",
                    "GITHUB_STEP_SUMMARY": str(raiz / "resumen.md")}), \
                    mock.patch.object(mr, "llamar_mistral", return_value=respuesta), \
                    mock.patch.object(mr, "publicar") as publicar, \
                    mock.patch("builtins.print"):
                self.assertEqual(mr.main(), 0)
            self.assertIn("Comprobaciones por lectura", publicar.call_args.args[2])

    def test_cambio_solo_de_permisos(self):
        with self.repositorio() as raiz:
            ruta = "ejecutable con espacio.py"
            archivo = raiz / ruta
            archivo.write_text("print('hola')\n", encoding="utf-8")
            archivo.chmod(0o644)
            base = self.commit()
            archivo.chmod(0o755)
            cabeza = self.commit()
            diff = self.comprobar(base, cabeza, ruta)
            self.assertIn("old mode 100644", diff)
            self.assertIn("new mode 100755", diff)

    def test_cambio_binario(self):
        with self.repositorio() as raiz:
            ruta = "datos.bin"
            archivo = raiz / ruta
            archivo.write_bytes(b"\0anterior\n")
            base = self.commit()
            archivo.write_bytes(b"\0nuevo\n")
            cabeza = self.commit()
            diff = self.comprobar(base, cabeza, ruta)
            self.assertIn("Binary files", diff)

    def test_inventario_respeta_exclusiones_y_ruta_de_eliminado(self):
        with self.repositorio() as raiz:
            generado = raiz / mr.EXCLUIDOS[0]
            generado.parent.mkdir(parents=True)
            generado.write_text("{}\n", encoding="utf-8")
            eliminado = raiz / "borrado.py"
            eliminado.write_text("resultado = 1\n", encoding="utf-8")
            base = self.commit()
            generado.write_text('{"cambio": 1}\n', encoding="utf-8")
            eliminado.unlink()
            cabeza = self.commit()
            self.assertEqual(mr.obtener_rutas_diff(base, cabeza), {"borrado.py"})


if __name__ == "__main__":
    unittest.main()
