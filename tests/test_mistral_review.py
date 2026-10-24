"""Script de revisión con Mistral (.github/scripts/mistral_review.py).

Sin red ni API: se prueban el diff, el prompt, el parseo del JSON, el
comentario y la publicación (con `subprocess` simulado).
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "mistral_review", os.path.join(_RAIZ, ".github", "scripts", "mistral_review.py"))
mr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mr)

HALLAZGO = {"severidad": "media", "archivo": "a.py", "fragmento": "x = `1`",
            "problema": "El ancla quita la marca", "escenario": "texto truncado -> eco_distinto",
            "arreglo": "conservar la marca"}


class TestDiff(unittest.TestCase):
    def test_excluye_generados_y_lleva_contexto(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                subprocess.run(["git", "-C", d] + list(a), check=True,
                               capture_output=True)
            git("init", "-q")
            git("config", "user.email", "t@t"); git("config", "user.name", "t")
            os.makedirs(os.path.join(d, "tests", "i18n"))
            with open(os.path.join(d, "a.py"), "w") as fh:
                fh.write("".join("l%d\n" % i for i in range(30)))
            with open(os.path.join(d, "tests", "i18n", "linea_base.json"), "w") as fh:
                fh.write("{}\n")
            git("add", "-A"); git("commit", "-qm", "base")
            base = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()
            with open(os.path.join(d, "a.py"), "a") as fh:
                fh.write("nuevo\n")
            with open(os.path.join(d, "tests", "i18n", "linea_base.json"), "w") as fh:
                fh.write('{"x": 1}\n')
            git("commit", "-qam", "cambio")
            viejo = os.getcwd()
            try:
                os.chdir(d)
                diff = mr.obtener_diff(base, "HEAD")
            finally:
                os.chdir(viejo)
        self.assertIn("+nuevo", diff)
        self.assertIn(" l20", diff)            # -U10: contexto amplio
        self.assertNotIn("linea_base.json", diff)


class TestPrompt(unittest.TestCase):
    def test_lleva_guia_titulo_y_diff_entero(self):
        msgs, recortado = mr.construir_mensajes("T", "D", "+x\n" * 10,
                                                ("CLAUDE.md", "regla 1"))
        u = msgs[1]["content"]
        self.assertFalse(recortado)
        for trozo in ("Guía del proyecto (CLAUDE.md)", "regla 1", "## Título\nT", "+x"):
            self.assertIn(trozo, u)
        self.assertIn("DATOS del PR", msgs[0]["content"])

    def test_recorta_y_lo_dice(self):
        diff = "+" + "x" * (mr.MAX_DIFF + 10)
        msgs, recortado = mr.construir_mensajes("T", None, diff, (None, ""))
        self.assertTrue(recortado)
        self.assertIn("recortado a %d" % mr.MAX_DIFF, msgs[1]["content"])
        self.assertNotIn("Guía del proyecto", msgs[1]["content"])


class TestRespuesta(unittest.TestCase):
    def test_interpreta_el_esquema(self):
        r = mr.interpretar(json.dumps({"resumen": "R", "hallazgos": [HALLAZGO, "x", {}]}))
        self.assertEqual(r, ("R", [HALLAZGO]))
        for malo in ("no json", "[]", json.dumps({"resumen": "R"}), None):
            self.assertIsNone(mr.interpretar(malo))

    def test_renderiza_hallazgos_ordenados(self):
        bajo = dict(HALLAZGO, severidad="baja", problema="menor")
        alto = dict(HALLAZGO, severidad="alta", problema="grave")
        md = mr.renderizar(("R", [bajo, alto]), "", "codestral-latest", 100, False)
        self.assertTrue(md.startswith(mr.MARCA))
        self.assertLess(md.index("grave"), md.index("menor"))
        self.assertIn("🔴 **alta** · `a.py`", md)
        self.assertIn("Escenario: texto truncado -> eco_distinto", md)
        self.assertIn("`x = '1'`", md)  # la comilla invertida no rompe el código

    def test_sin_hallazgos_y_formato_raro(self):
        self.assertIn("**Sin hallazgos.**",
                      mr.renderizar(("R", []), "", "m", 1, False))
        md = mr.renderizar(None, "texto libre", "m", 200000, True)
        self.assertIn("texto libre", md)
        self.assertIn("recortado de 200000", md)


class TestPublicar(unittest.TestCase):
    def _run(self, ids):
        llamadas = []

        def falso(args, **kw):
            llamadas.append(args)
            return mock.Mock(stdout=ids)
        with mock.patch.object(mr.subprocess, "run", side_effect=falso):
            mr.publicar("o/r", 7, "cuerpo")
        return llamadas

    def test_edita_el_comentario_existente(self):
        llamadas = self._run("11\n22\n")
        self.assertIn("PATCH", llamadas[1])
        self.assertIn("repos/o/r/issues/comments/22", llamadas[1])

    def test_crea_si_no_hay(self):
        llamadas = self._run("")
        self.assertIn("POST", llamadas[1])
        self.assertIn("repos/o/r/issues/7/comments", llamadas[1])


class TestSinClave(unittest.TestCase):
    def test_sin_clave_no_falla(self):
        with mock.patch.dict(os.environ, {"MISTRAL_API_KEY": ""}):
            self.assertEqual(mr.main(), 0)


if __name__ == "__main__":
    unittest.main()
