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
COMPROBACION = {"archivo": "a.py", "escenario": "entrada vacía",
               "conclusion": "la guarda devuelve error antes de escribir",
               "estado": "revisado"}


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
        self.assertIn("[Mistral AI (@mistralai)](https://github.com/mistralai)", md)
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
    def test_dos_resultados_crean_comentarios_sin_editar_ni_leer_el_historial(self):
        anterior = {"body": mr.MARCA + "\nRevisión anterior"}
        comentarios = [dict(anterior)]

        def crear(comando, **kwargs):
            self.assertEqual(comando, ["gh", "api", "-X", "POST",
                "repos/o/r/issues/7/comments", "--input", "-"])
            comentarios.append(json.loads(kwargs["input"]))
            return mock.Mock(stdout="{}")

        cuerpos = ["cuerpo con \"comillas\"\ny saltos",
                   mr.renderizar(None, "m", 1, False, error="fallo de API")]
        with mock.patch.object(mr.subprocess, "run", side_effect=crear) as run:
            for cuerpo in cuerpos:
                mr.publicar("o/r", 7, cuerpo)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(comentarios, [anterior] + [{"body": c} for c in cuerpos])

    def test_error_al_crear_se_propaga_sin_intentar_editar_otros_comentarios(self):
        with mock.patch.object(mr.subprocess, "run", side_effect=
                subprocess.CalledProcessError(1, "gh")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                mr.publicar("o/r", 7, "cuerpo")
        run.assert_called_once()


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

    def ejecutar(self, respuesta=None, fallo=None, entorno=None):
        if respuesta and respuesta.startswith("{"):
            datos = json.loads(respuesta)
            datos.setdefault("comprobaciones", [COMPROBACION])
            respuesta = json.dumps(datos)
        evento = json.dumps({"pull_request": {
            "number": 7, "base": {"sha": "base"}, "head": {"sha": "abc123"}}})
        variables = {"MISTRAL_API_KEY": "clave", "GITHUB_EVENT_PATH": "evento.json",
                     "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": ""}
        variables.update(entorno or {})
        with mock.patch.dict(os.environ, variables), \
                mock.patch("builtins.open", mock.mock_open(read_data=evento)), \
                mock.patch.object(mr, "obtener_diff", return_value=self.DIFF), \
                mock.patch.object(mr, "obtener_rutas_diff", return_value={"a.py"}), \
                mock.patch.object(mr, "leer_guia", return_value=(None, "")), \
                mock.patch.object(mr, "obtener_contexto", return_value="contexto"), \
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

    def test_fallo_de_api_publica_informe_sin_filtrar_detalles(self):
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
                self.assertNotIn("sustituye", cuerpo)

    def test_cada_intento_del_mismo_commit_identifica_su_ejecucion_en_todos_los_estados(self):
        for intento in ("1", "2"):
            for respuesta, fallo in ((json.dumps({"resumen": "R", "hallazgos": []}), None),
                                     ("no json", None), (None, TimeoutError())):
                with self.subTest(intento=intento, respuesta=respuesta, fallo=fallo):
                    _, cuerpo = self.ejecutar(respuesta, fallo, entorno={
                        "GITHUB_SERVER_URL": "https://github.example.test/",
                        "GITHUB_RUN_ID": "123456", "GITHUB_RUN_ATTEMPT": intento})
                    self.assertIn("Commit revisado: `abc123`", cuerpo)
                    self.assertIn("https://github.example.test/o/r/actions/runs/123456/attempts/"
                                  + intento, cuerpo)
                    self.assertIn("intento %s" % intento, cuerpo)

    def test_fuera_de_actions_no_inventa_un_enlace(self):
        _, cuerpo = self.ejecutar(json.dumps({"resumen": "R", "hallazgos": []}))
        self.assertNotIn("/actions/runs/", cuerpo)

    def test_evidencia_fuera_de_la_parte_enviada_no_cuenta(self):
        with mock.patch.object(mr, "MAX_DIFF", self.DIFF.index("+x = `1`")):
            codigo, cuerpo = self.ejecutar(json.dumps(
                {"resumen": "R", "hallazgos": [HALLAZGO]}))
        self.assertEqual(codigo, 1)
        self.assertIn("Revisión no válida", cuerpo)

    def test_diff_vacio_no_consulta_api_ni_exige_casos_inventados(self):
        with mock.patch.object(self, "DIFF", ""):
            codigo, cuerpo = self.ejecutar(fallo=AssertionError("no llamar API"))
        self.assertEqual(codigo, 0)
        self.assertIn("No hay diff revisable", cuerpo)


class TestSinClave(unittest.TestCase):
    def test_sin_clave_no_falla(self):
        with mock.patch.dict(os.environ, {"MISTRAL_API_KEY": ""}):
            self.assertEqual(mr.main(), 0)


class TestComprobaciones(unittest.TestCase):
    def test_diagnostico_distingue_rechazos_sin_exponer_contenido(self):
        base = {"resumen": "R", "hallazgos": [], "comprobaciones": [COMPROBACION]}
        casos = [
            ("dato privado", "json_invalido"),
            (dict(base, hallazgos=None), "hallazgos_no_lista"),
            (dict(base, resumen=""), "resumen_invalido"),
            (dict(base, comprobaciones=[]), "comprobaciones_cantidad_o_tipo"),
            (dict(base, comprobaciones=[{}]), "comprobacion_0_campos_invalidos"),
            (dict(base, comprobaciones=[dict(COMPROBACION, estado="dato privado")]),
             "comprobacion_0_estado_invalido"),
            (dict(base, comprobaciones=[dict(COMPROBACION, archivo="dato privado")]),
             "comprobacion_0_archivo_fuera_del_pr"),
            (dict(base, hallazgos=[{}]), "hallazgo_0_campos_invalidos"),
            (dict(base, hallazgos=[dict(HALLAZGO, severidad="dato privado")]),
             "hallazgo_0_severidad_invalida"),
            (dict(base, hallazgos=[dict(HALLAZGO, fragmento="dato privado")]),
             "hallazgo_0_cita_fuera_del_diff"),
        ]
        for datos, esperado in casos:
            with self.subTest(codigo=esperado):
                diagnostico = []
                texto = datos if isinstance(datos, str) else json.dumps(datos)
                self.assertIsNone(mr.interpretar(texto, TestMain.DIFF, True,
                                                diagnostico=diagnostico))
                self.assertEqual(diagnostico, [esperado])
                self.assertNotIn('dato privado', str(diagnostico))
        diagnostico = []
        self.assertIsNotNone(mr.interpretar(json.dumps(base), TestMain.DIFF, True,
                                           diagnostico=diagnostico))
        self.assertEqual(diagnostico, [])

    def test_exige_escenarios_y_rutas_del_diff_sin_aceptar_exito_vacio(self):
        base = {"resumen": "R", "hallazgos": [], "comprobaciones": [COMPROBACION]}
        self.assertIsNotNone(mr.interpretar(json.dumps(base), TestMain.DIFF, True))
        for valor in (None, [], [{}], [dict(COMPROBACION, estado="ejecutado")],
                      [dict(COMPROBACION, escenario="")],
                      [dict(COMPROBACION, archivo="inventado.py")]):
            with self.subTest(valor=valor):
                self.assertIsNone(mr.interpretar(json.dumps(dict(
                    base, comprobaciones=valor)), TestMain.DIFF, True))
        del base["comprobaciones"]
        self.assertIsNone(mr.interpretar(json.dumps(base), TestMain.DIFF, True))

    def test_renderiza_casos_pendientes_como_lectura_no_como_tests_ejecutados(self):
        md = mr.renderizar(("R", []), "m", 10, False,
            comprobaciones=[dict(COMPROBACION, estado="pendiente")])
        self.assertIn("sin ejecutar tests", md)
        self.assertIn("**pendiente**", md)
        self.assertIn(COMPROBACION["escenario"], md)

    def test_contexto_del_commit_acotado_y_enviado_como_datos(self):
        with mock.patch.object(mr.subprocess, "run", return_value=mock.Mock(
                returncode=0, stdout=b"def funcion():\n    pass\n")) as run, \
                mock.patch.object(mr, "MAX_ARCHIVO", 12):
            contexto = mr.obtener_contexto(TestMain.DIFF, "abc123")
        self.assertEqual(run.call_args.args[0], ["git", "show", "abc123:a.py"])
        self.assertIn("contexto recortado", contexto)
        self.assertNotIn("pass", contexto)
        mensajes, _ = mr.construir_mensajes("T", "D", TestMain.DIFF,
                                           (None, ""), contexto)
        self.assertIn(contexto, mensajes[1]["content"])

    def test_resumen_sobrevive_a_fallo_de_publicacion(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "resumen.md")
            with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ruta}), \
                    mock.patch.object(mr, "publicar", side_effect=OSError("privado")):
                # El helper anterior verifica publicación correcta; aquí main se
                # ejecuta directamente para comprobar el fallo de permisos.
                evento = json.dumps({"pull_request": {"number": 7,
                    "head": {"sha": "abc123"}, "base": {"sha": "base"}}})
                with mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "clave",
                        "GITHUB_EVENT_PATH": "evento", "GITHUB_REPOSITORY": "o/r"}), \
                        mock.patch.object(mr, "obtener_diff", return_value=TestMain.DIFF), \
                        mock.patch.object(mr, "obtener_rutas_diff", return_value={"a.py"}), \
                        mock.patch.object(mr, "obtener_contexto", return_value=""), \
                        mock.patch.object(mr, "leer_guia", return_value=(None, "")), \
                        mock.patch.object(mr, "llamar_mistral", return_value=json.dumps({
                            "resumen": "R", "hallazgos": [],
                            "comprobaciones": [COMPROBACION]})), \
                        mock.patch("builtins.open", mock.mock_open(read_data=evento)) as abrir, \
                        mock.patch("builtins.print"):
                    self.assertEqual(mr.main(), 1)
                    abrir.assert_any_call(ruta, "a", encoding="utf-8")
                    escrito = abrir().write.call_args.args[0]
                    self.assertIn("Comprobaciones por lectura", escrito)

    def test_sin_clave_deja_motivo_en_resumen(self):
        with mock.patch.dict(os.environ, {"MISTRAL_API_KEY": ""}), \
                mock.patch.object(mr, "escribir_resumen") as resumen, \
                mock.patch("builtins.print"):
            self.assertEqual(mr.main(), 0)
        self.assertIn("omitida", resumen.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
