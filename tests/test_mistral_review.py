"""Script de revisión con Mistral (.github/scripts/mistral_review.py).

Sin red ni API: se prueban el diff, el prompt, el parseo del JSON, el
comentario y la publicación (con `subprocess` simulado).
"""
from datetime import datetime, timezone
import io
import urllib.error
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
        r = mr.interpretar(json.dumps({"resumen": "R", "hallazgos": [HALLAZGO]}))
        self.assertEqual(r, ("R", [HALLAZGO]))
        for malo in ("no json", "[]", json.dumps({"resumen": "R"}), None):
            self.assertIsNone(mr.interpretar(malo))

    def test_rechaza_hallazgos_incompletos_sin_convertirlos_en_exito(self):
        for campo in HALLAZGO:
            for valor in (None, "", "  ", [], 123):
                with self.subTest(campo=campo, valor=valor):
                    malo = dict(HALLAZGO, **{campo: valor})
                    self.assertIsNone(mr.interpretar(json.dumps(
                        {"resumen": "R", "hallazgos": [HALLAZGO, malo]})))
        for malo in ({}, "x", dict(HALLAZGO, severidad="crítica")):
            self.assertIsNone(mr.interpretar(json.dumps(
                {"resumen": "R", "hallazgos": [malo]})))

    def test_resumen_obligatorio_y_revision_parcial(self):
        for resumen in (None, [], 123, "", "  "):
            self.assertIsNone(mr.interpretar(json.dumps(
                {"resumen": resumen, "hallazgos": []})))
        md = mr.renderizar(("R", []), "m", mr.MAX_DIFF + 1, True)
        self.assertIn("Sin hallazgos en la parte revisada", md)
        self.assertNotIn("**Sin hallazgos.**", md)

    def test_renderiza_hallazgos_ordenados(self):
        bajo = dict(HALLAZGO, severidad="baja", problema="menor")
        alto = dict(HALLAZGO, severidad="alta", problema="grave")
        md = mr.renderizar(("R", [bajo, alto]), "codestral-latest", 100, False)
        self.assertTrue(md.startswith(mr.MARCA))
        self.assertLess(md.index("grave"), md.index("menor"))
        self.assertIn("🔴 **alta** · `a.py`", md)
        self.assertIn("Escenario: texto truncado -> eco_distinto", md)
        self.assertIn("`x = '1'`", md)  # la comilla invertida no rompe el código

    def test_sin_hallazgos_y_formato_raro(self):
        self.assertIn("**Sin hallazgos.**",
                      mr.renderizar(("R", []), "m", 1, False))
        md = mr.renderizar(None, "m", 200000, True)
        self.assertIn("Revisión no válida", md)
        self.assertNotIn("texto libre", md)
        self.assertIn("recortado de 200000", md)


class TestPublicar(unittest.TestCase):
    def comentario(self, id, login="github-actions[bot]", tipo="Bot", cuerpo=mr.MARCA):
        return {"id": id, "user": {"login": login, "type": tipo}, "body": cuerpo}

    def publicar(self, paginas):
        with mock.patch.object(mr.subprocess, "run", return_value=mock.Mock(
                stdout=json.dumps(paginas))) as run:
            mr.publicar("o/r", 7, "cuerpo con \"comillas\"\ny saltos")
        return run.call_args_list

    def test_edita_el_ultimo_comentario_propio_entre_paginas(self):
        llamadas = self.publicar([[self.comentario(11)], [self.comentario(22),
            self.comentario(33, "persona", "User"), self.comentario(44, "otro[bot]")]])
        self.assertIn("--paginate", llamadas[0].args[0])
        self.assertIn("--slurp", llamadas[0].args[0])
        self.assertIn("PATCH", llamadas[1].args[0])
        self.assertIn("repos/o/r/issues/comments/22", llamadas[1].args[0])
        self.assertEqual(json.loads(llamadas[1].kwargs["input"]),
                         {"body": "cuerpo con \"comillas\"\ny saltos"})

    def test_crea_si_no_hay_comentario_propio_con_marca(self):
        for paginas in ([[]], [[self.comentario(33, "persona", "User"),
                                self.comentario(44, "otro[bot]"),
                                self.comentario(55, cuerpo="otra revisión")]]):
            with self.subTest(paginas=paginas):
                llamadas = self.publicar(paginas)
                self.assertIn("POST", llamadas[1].args[0])
                self.assertIn("repos/o/r/issues/7/comments", llamadas[1].args[0])


class TestAPI(unittest.TestCase):
    def respuesta(self, contenido="{}", fin="stop"):
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = json.dumps({
            "choices": [{"message": {"content": contenido}, "finish_reason": fin}]
        }).encode()
        return resp

    def error(self, codigo, detalle="", headers=None):
        return urllib.error.HTTPError(mr.API, codigo, "error", headers or {},
                                      io.BytesIO(detalle.encode()))

    def test_reintenta_transitorios(self):
        for error in (self.error(429), self.error(503),
                      urllib.error.URLError("red"), TimeoutError()):
            with self.subTest(error=error), mock.patch.object(
                    mr.urllib.request, "urlopen", side_effect=[error, self.respuesta()]) as abrir, \
                    mock.patch.object(mr.time, "sleep"):
                self.assertEqual(mr.llamar_mistral([], "m", "clave"), "{}")
                self.assertEqual(abrir.call_count, 2)

    def test_limite_reintentos_y_errores_permanentes(self):
        for codigo, llamadas in ((503, 3), (401, 1), (400, 1)):
            with self.subTest(codigo=codigo), mock.patch.object(
                    mr.urllib.request, "urlopen", side_effect=self.error(codigo)) as abrir, \
                    mock.patch.object(mr.time, "sleep"):
                with self.assertRaises(urllib.error.HTTPError):
                    mr.llamar_mistral([], "m", "clave")
                self.assertEqual(abrir.call_count, llamadas)

    def test_fallback_solo_por_formato_no_soportado(self):
        with mock.patch.object(mr.urllib.request, "urlopen", side_effect=[
                self.error(400, "response_format json_object is not supported"),
                self.respuesta()]) as abrir:
            mr.llamar_mistral([], "m", "clave")
        cuerpos = [json.loads(c.args[0].data) for c in abrir.call_args_list]
        self.assertIn("response_format", cuerpos[0])
        self.assertNotIn("response_format", cuerpos[1])

    def test_rechaza_salida_truncada_o_vacia(self):
        for contenido, fin in (("{}", "length"), (None, "stop"), ("", "stop"),
                               ("{}", "model_length"), ("{}", "error")):
            with self.subTest(contenido=contenido, fin=fin), mock.patch.object(
                    mr.urllib.request, "urlopen", return_value=self.respuesta(contenido, fin)):
                with self.assertRaises(ValueError):
                    mr.llamar_mistral([], "m", "clave")


    def test_retry_after_segundos_fecha_y_valor_invalido(self):
        ahora = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        for valor, espera in (("30", 30), ("Sun, 25 Oct 2026 12:00:40 GMT", 40),
                              ("no válido", 1)):
            with self.subTest(valor=valor), mock.patch.object(
                    mr.urllib.request, "urlopen", side_effect=[
                        self.error(429, headers={"Retry-After": valor}), self.respuesta()]), \
                    mock.patch.object(mr.time, "sleep") as dormir, \
                    mock.patch.object(mr, "datetime") as reloj:
                reloj.now.return_value = ahora
                mr.llamar_mistral([], "m", "clave")
                dormir.assert_called_once_with(espera)

    def test_no_reintenta_antes_de_un_retry_after_excesivo(self):
        with mock.patch.object(mr.urllib.request, "urlopen", side_effect=self.error(
                429, headers={"Retry-After": "3600"})) as abrir, \
                mock.patch.object(mr.time, "sleep") as dormir:
            with self.assertRaises(urllib.error.HTTPError):
                mr.llamar_mistral([], "m", "clave")
            self.assertEqual(abrir.call_count, 1)
            dormir.assert_not_called()

    def test_fallback_comparte_el_limite_de_tres_solicitudes(self):
        with mock.patch.object(mr.urllib.request, "urlopen", side_effect=[
                self.error(503), self.error(400, "json_object is unsupported"),
                self.error(503)]) as abrir, mock.patch.object(mr.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                mr.llamar_mistral([], "m", "clave")
            self.assertEqual(abrir.call_count, 3)
            self.assertNotIn("response_format", json.loads(abrir.call_args.args[0].data))

    def test_estructura_de_api_invalida_da_error_controlado(self):
        for cuerpo in ({}, {"choices": []}, {"choices": [None]}, {"choices": [{}]}, None):
            resp = mock.MagicMock()
            resp.__enter__.return_value.read.return_value = json.dumps(cuerpo).encode()
            with self.subTest(cuerpo=cuerpo), mock.patch.object(
                    mr.urllib.request, "urlopen", return_value=resp):
                with self.assertRaises(ValueError):
                    mr.llamar_mistral([], "m", "clave")


class TestMain(unittest.TestCase):
    DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x = 0\n+x = `1`\n"

    def ejecutar(self, respuesta=None, fallo=None):
        evento = json.dumps({"pull_request": {
            "number": 7, "base": {"sha": "base"}, "head": {"sha": "abc123"}}})
        with mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "clave",
                    "GITHUB_EVENT_PATH": "evento.json", "GITHUB_REPOSITORY": "o/r"}), \
                mock.patch("builtins.open", mock.mock_open(read_data=evento)), \
                mock.patch.object(mr, "obtener_diff", return_value=self.DIFF), \
                mock.patch.object(mr, "leer_guia", return_value=(None, "")), \
                mock.patch.object(mr, "llamar_mistral", return_value=respuesta, side_effect=fallo), \
                mock.patch.object(mr, "publicar") as publicar, mock.patch("builtins.print"):
            codigo = mr.main()
        publicar.assert_called_once()
        return codigo, publicar.call_args.args[2]

    def test_respuesta_invalida_publica_aviso_y_falla_el_check(self):
        for texto, codigo in (("no json", 1),
                (json.dumps({"resumen": "R", "hallazgos": []}), 0),
                (json.dumps({"resumen": "R", "hallazgos": [HALLAZGO]}), 0),
                (json.dumps({"resumen": "R", "hallazgos": [dict(
                    HALLAZGO, archivo="inventado.py")]}), 1)):
            with self.subTest(texto=texto):
                resultado, cuerpo = self.ejecutar(texto)
                self.assertEqual(resultado, codigo)
                self.assertIn("Commit revisado: `abc123`", cuerpo)
                if codigo:
                    self.assertIn("Revisión no válida", cuerpo)
                    self.assertNotIn("**Sin hallazgos.**", cuerpo)

    def test_fallo_de_api_sustituye_el_resultado_anterior_sin_filtrar_detalles(self):
        fallos = (TimeoutError("dato privado"), urllib.error.URLError("dato privado"),
                  ValueError("dato privado"),
                  urllib.error.HTTPError(mr.API, 401, "dato privado", {}, None))
        for fallo in fallos:
            with self.subTest(fallo=fallo):
                codigo, cuerpo = self.ejecutar(fallo=fallo)
                self.assertEqual(codigo, 1)
                self.assertIn("Revisión no completada", cuerpo)
                self.assertIn("Commit revisado: `abc123`", cuerpo)
                self.assertNotIn("dato privado", cuerpo)
                self.assertNotIn("Sin hallazgos", cuerpo)

    def test_evidencia_fuera_de_la_parte_enviada_no_cuenta(self):
        with mock.patch.object(mr, "MAX_DIFF", self.DIFF.index("+x = `1`")):
            codigo, cuerpo = self.ejecutar(json.dumps(
                {"resumen": "R", "hallazgos": [HALLAZGO]}))
        self.assertEqual(codigo, 1)
        self.assertIn("Revisión no válida", cuerpo)


class TestSinClave(unittest.TestCase):
    def test_sin_clave_no_falla(self):
        with mock.patch.dict(os.environ, {"MISTRAL_API_KEY": ""}):
            self.assertEqual(mr.main(), 0)


if __name__ == "__main__":
    unittest.main()
