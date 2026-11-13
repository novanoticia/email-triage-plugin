"""Utilidad de la revisión de Mistral (cambios del 2026-11-11).

Origen: en los PR #198 y #199 cada commit recibía dos informes distintos, con
seis comprobaciones «revisado» que repetían la descripción del PR, y el
contexto enviado de `triage_helpers.py` era su docstring. Sin red ni API.
Lo que estos tests fijan es mecánico (qué se envía, qué se publica y cuándo);
la calidad del razonamiento del modelo no se puede probar aquí.
"""
import importlib.util
import json
import os
import subprocess
import unittest
from unittest import mock

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "mistral_review", os.path.join(_RAIZ, ".github", "scripts", "mistral_review.py"))
mr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mr)

# Archivo largo: 400 líneas de relleno antes de las funciones que cambian.
FUENTE = '"""Docstring del módulo."""\n' + "".join(
    "RELLENO_%d = %d\n" % (i, i) for i in range(400)) + '''

class Motor:
    def otro(self):
        return "no enviado"

    @staticmethod
    def umbral(valor, tope=4):
        if valor is None:
            return tope
        def recorta(x):
            return min(x, tope)
        return recorta(valor)


def suelta():
    return "tampoco"

CONSTANTE = 1
'''
LINEAS = FUENTE.split("\n")
N_UMBRAL = LINEAS.index("    def umbral(valor, tope=4):") + 1     # 1-indexado
N_RECORTA = LINEAS.index("            return min(x, tope)") + 1
N_CONSTANTE = LINEAS.index("CONSTANTE = 1") + 1


def diff_de(ruta, numero, linea):
    return ("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -%d,2 +%d,2 @@\n"
            " contexto\n-vieja\n+%s\n" % (ruta, ruta, ruta, ruta,
                                          numero - 1, numero - 1, linea))


class TestLineasCambiadas(unittest.TestCase):
    def test_numera_en_la_cabeza_y_no_cuenta_el_contexto(self):
        diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
                "@@ -10,4 +20,5 @@ def f():\n c1\n-quitada\n+nueva1\n+nueva2\n c2\n c3\n"
                "@@ -40 +51,0 @@\n-solo borrada\n")
        # De una eliminada cuentan las dos líneas que la rodeaban: 20 y 21
        # para «quitada», 50 y 51 para el borrado puro. c2 y c3 no cuentan.
        self.assertEqual(mr.lineas_cambiadas(diff), {"a.py": {20, 21, 22, 50, 51}})

    def test_el_indice_de_citas_no_cambia(self):
        diff = diff_de("a.py", 5, "x = 1")
        self.assertEqual(mr.indice_diff(diff), {"a.py": {" contexto", "-vieja", "+x = 1"}})

    def test_archivo_sin_hunks_no_tiene_lineas(self):
        diff = "diff --git a/a.py b/b.py\nsimilarity index 100%\nrename from a.py\nrename to b.py\n"
        self.assertEqual(mr.lineas_cambiadas(diff), {})


class TestRangos(unittest.TestCase):
    def test_metodo_con_decorador_sin_el_resto_de_la_clase(self):
        (inicio, fin, nombre), = mr._rangos_python(FUENTE, {N_UMBRAL + 1})
        self.assertEqual(nombre, "Motor.umbral")
        self.assertEqual(LINEAS[inicio - 1].strip(), "@staticmethod")
        self.assertEqual(LINEAS[fin - 1].strip(), "return recorta(valor)")

    def test_un_cierre_va_con_su_funcion_y_no_se_duplica(self):
        rangos = mr._rangos_python(FUENTE, {N_RECORTA, N_UMBRAL})
        self.assertEqual([r[2] for r in rangos], ["Motor.umbral"])

    def test_fuera_de_funcion_va_una_ventana(self):
        (inicio, fin, nombre), = mr._rangos_python(FUENTE, {N_CONSTANTE})
        self.assertEqual(nombre, "")
        self.assertEqual(inicio, N_CONSTANTE - mr.VENTANA)
        self.assertLessEqual(fin, len(LINEAS))

    def test_expresion_muy_profunda_no_agota_la_recursion(self):
        fuente = "def f():\n    return " + " + ".join("v%d" % i for i in range(3000)) + "\n"
        self.assertEqual(mr._rangos_python(fuente, {2}), [(1, 2, "f")])

    def test_funcion_dentro_de_un_if_o_try_tambien_se_encuentra(self):
        fuente = "try:\n    import x\nexcept ImportError:\n    def x():\n        return 1\n"
        self.assertEqual(mr._rangos_python(fuente, {5}), [(4, 5, "x")])

    def test_codigo_que_no_parsea_no_lanza(self):
        self.assertIsNone(mr._rangos_python("def roto(:\n", {1}))


class TestContexto(unittest.TestCase):
    def contexto(self, diff, fuentes):
        def git_show(orden, **_):
            ruta = orden[2].split(":", 1)[1]
            if ruta not in fuentes:
                return mock.Mock(returncode=128, stdout=b"")
            return mock.Mock(returncode=0, stdout=fuentes[ruta].encode("utf-8"))
        with mock.patch.object(mr.subprocess, "run", side_effect=git_show) as run:
            texto = mr.obtener_contexto(diff, "abc123")
        for llamada in run.call_args_list:
            self.assertEqual(llamada.args[0][:2], ["git", "show"])   # nunca ejecuta el PR
        return texto

    def test_envia_la_funcion_cambiada_y_no_el_principio_del_archivo(self):
        texto = self.contexto(diff_de("motor.py", N_RECORTA, "return min(x, tope)"),
                              {"motor.py": FUENTE})
        self.assertIn("if valor is None:", texto)          # la guarda de la función
        self.assertIn("Motor.umbral", texto)
        self.assertIn("# líneas %d-" % (N_UMBRAL - 1), texto)
        self.assertNotIn("RELLENO_0 ", texto)
        self.assertNotIn("no enviado", texto)
        self.assertNotIn("tampoco", texto)
        self.assertNotIn("contexto recortado", texto)

    def test_borrar_la_ultima_linea_de_una_funcion_larga_la_envia_entera(self):
        larga = "def larga(x):\n    if x is None:\n        return 0\n" + "".join(
            "    x += %d\n" % i for i in range(60)) + "\n\nDESPUES = 1\n"
        ultima = larga.split("\n").index("    x += 59") + 1
        # Se borró el `return x` que seguía a la línea `ultima`.
        diff = ("diff --git a/l.py b/l.py\n--- a/l.py\n+++ b/l.py\n"
                "@@ -%d,2 +%d,1 @@\n     x += 59\n-    return x\n" % (ultima, ultima))
        texto = self.contexto(diff, {"l.py": larga})
        self.assertIn("· larga", texto)
        self.assertIn("if x is None:", texto)    # a 60 líneas: fuera de la ventana

    def test_el_codigo_va_antes_que_los_tests(self):
        diff = (diff_de("tests/test_a.py", N_RECORTA, "x") +
                diff_de("zeta.py", N_RECORTA, "x") + diff_de("README.md", 3, "x"))
        texto = self.contexto(diff, {"tests/test_a.py": FUENTE, "zeta.py": FUENTE})
        self.assertLess(texto.index("## zeta.py"), texto.index("## tests/test_a.py"))
        self.assertNotIn("README.md", texto)               # solo Python

    def test_presupuesto_por_lineas_enteras_y_visible(self):
        with mock.patch.object(mr, "MAX_ARCHIVO", 120):
            texto = self.contexto(diff_de("motor.py", N_RECORTA, "x"), {"motor.py": FUENTE})
        self.assertIn("contexto recortado: Motor.umbral", texto)
        self.assertIn("@staticmethod", texto)
        self.assertNotIn("return recorta(valor)", texto)
        for linea in texto.split("```python\n", 1)[1].split("\n```")[0].split("\n")[1:]:
            self.assertIn(linea, LINEAS)                    # ninguna línea partida

    def test_presupuesto_total_y_archivo_ausente(self):
        diff = diff_de("a.py", N_RECORTA, "x") + diff_de("b.py", N_RECORTA, "x") + \
            diff_de("borrado.py", 2, "x")
        with mock.patch.object(mr, "MAX_CONTEXTO", 100):
            texto = self.contexto(diff, {"a.py": FUENTE, "b.py": FUENTE})
        self.assertIn("## a.py", texto)
        self.assertNotIn("## b.py", texto)                 # sin bloque vacío
        self.assertIn("Contexto de b.py omitido por presupuesto: Motor.umbral", texto)
        with mock.patch.object(mr, "MAX_CONTEXTO", 0):
            self.assertEqual(self.contexto(diff, {"a.py": FUENTE}),
                             "Contexto adicional omitido: presupuesto agotado.")
        self.assertIn("Archivo no disponible en cabeza: borrado.py",
                      self.contexto(diff_de("borrado.py", 2, "x"), {}))

    def test_sin_sintaxis_valida_usa_ventanas(self):
        roto = "def roto(:\n" + "".join("linea %d\n" % i for i in range(100))
        texto = self.contexto(diff_de("roto.py", 50, "x"), {"roto.py": roto})
        self.assertIn("linea 48", texto)
        self.assertNotIn("linea 90", texto)


class TestGuia(unittest.TestCase):
    def test_la_guia_del_repo_cabe_entera(self):
        nombre, texto = mr.leer_guia(_RAIZ)
        with open(os.path.join(_RAIZ, nombre), encoding="utf-8") as fh:
            self.assertEqual(texto, fh.read())
        self.assertIn("Gotchas conocidos", texto)           # el final de CLAUDE.md

    def test_si_se_recorta_lo_dice(self):
        with mock.patch.object(mr, "MAX_GUIA", 50):
            _, texto = mr.leer_guia(_RAIZ)
        self.assertIn("Guía recortada a 50 caracteres", texto)


class TestPrompt(unittest.TestCase):
    def test_pide_romper_y_refutar_sin_cambiar_el_esquema(self):
        for trozo in ("ROMPER", "refutar", '"pendiente"', "el test X lo cubre",
                      '"estado" ("revisado" o "pendiente")', "DATOS del PR"):
            self.assertIn(trozo, mr.SISTEMA)


COMPROBACIONES = [
    {"archivo": "a.py", "escenario": "lista vacía", "conclusion": "devuelve []",
     "estado": "revisado"},
    {"archivo": "a.py", "escenario": "config sin tocar", "conclusion": "falta ver cargar()",
     "estado": "pendiente"}]
HALLAZGO = {"severidad": "alta", "archivo": "a.py", "fragmento": "x = 1",
            "problema": "P", "escenario": "E", "arreglo": "A"}


class TestInforme(unittest.TestCase):
    def test_lo_accionable_arriba_y_lo_revisado_plegado(self):
        md = mr.renderizar(("R", [HALLAZGO]), "m", 10, False, cabeza="c1", base="b1",
                           comprobaciones=COMPROBACIONES)
        self.assertIn("**Resultado:** 1 hallazgo(s) · 1 comprobación(es) pendiente(s) "
                      "· 1 sin defecto aparente.", md)
        orden = [md.index(x) for x in ("**Resultado:**", "### Hallazgos (1)",
                                       "pendientes (1)", "falta ver cargar()",
                                       "<details>", "devuelve []", "</details>")]
        self.assertEqual(orden, sorted(orden))
        self.assertIn("\n\n<details>\n<summary>", md)        # GitHub exige las líneas en blanco
        self.assertIn("</summary>\n\n- ", md)

    def test_sin_comprobaciones_de_un_tipo_no_deja_secciones_vacias(self):
        md = mr.renderizar(("R", []), "m", 10, False, comprobaciones=COMPROBACIONES[:1])
        self.assertNotIn("pendientes (", md)
        self.assertIn("**Sin hallazgos.**", md)
        md = mr.renderizar(("R", []), "m", 10, False, comprobaciones=COMPROBACIONES[1:])
        self.assertNotIn("<details>", md)

    def test_la_marca_de_valido_solo_va_en_informes_validos(self):
        marca = mr.MARCA_OK % ("b1", "c1")
        valido = mr.renderizar(("R", []), "m", 10, False, cabeza="c1", base="b1")
        self.assertTrue(valido.startswith(mr.MARCA + "\n" + marca))
        for md in (mr.renderizar(None, "m", 10, False, cabeza="c1", base="b1"),
                   mr.renderizar(None, "m", 10, False, cabeza="c1", base="b1", error="API"),
                   mr.renderizar(("R", []), "m", 10, False, cabeza="c1")):
            self.assertNotIn("mistral-review-ok", md)


class TestNoRepetir(unittest.TestCase):
    B1, C1 = "b" * 40, "c" * 40

    def test_consulta_solo_la_cabecera_de_los_comentarios_de_actions(self):
        with mock.patch.object(mr.subprocess, "run",
                               return_value=mock.Mock(stdout="false\ntrue\n")) as run:
            self.assertTrue(mr.ya_revisado("o/r", 7, self.B1, self.C1))
        orden = run.call_args.args[0]
        self.assertIn("repos/o/r/issues/7/comments?per_page=100", orden)
        self.assertNotIn("POST", orden)                              # solo lee
        filtro = orden[orden.index("--jq") + 1]
        self.assertIn('.user.login == "github-actions[bot]"', filtro)
        # Misma base y misma cabeza, y al principio del cuerpo, no en cualquier parte.
        self.assertIn("startswith(%s)" % json.dumps(
            mr.MARCA + "\n" + mr.MARCA_OK % (self.B1, self.C1) + "\n"), filtro)
        with mock.patch.object(mr.subprocess, "run",
                               return_value=mock.Mock(stdout="false\nfalse\n")):
            self.assertFalse(mr.ya_revisado("o/r", 7, self.B1, self.C1))

    def test_la_cabecera_consultada_es_la_de_un_informe_valido_y_no_la_de_uno_rechazado(self):
        marca = mr.MARCA_OK % (self.B1, self.C1)
        cabecera = mr.MARCA + "\n" + marca + "\n"
        valido = mr.renderizar(("R", []), "m", 1, False, cabeza=self.C1, base=self.B1)
        self.assertTrue(valido.startswith(cabecera))
        # Respuesta rechazada cuyo texto repite la marca: no empieza por ella.
        rechazado = mr.renderizar(None, "m", 1, False, cabeza=self.C1, base=self.B1,
                                  sin_verificar=[(dict(HALLAZGO, problema=marca), "parcial")])
        self.assertIn("mistral-review-ok", rechazado)
        self.assertFalse(rechazado.startswith(cabecera))

    def test_no_interpola_en_el_filtro_nada_que_no_sea_un_sha(self):
        with mock.patch.object(mr.subprocess, "run") as run:
            self.assertFalse(mr.ya_revisado("o/r", 7, self.B1, 'c")) or true #'))
            self.assertFalse(mr.ya_revisado("o/r", 7, "", self.C1))
        run.assert_not_called()

    def test_si_no_se_puede_leer_el_historial_se_revisa(self):
        for fallo in (OSError(), subprocess.CalledProcessError(1, "gh")):
            with mock.patch.object(mr.subprocess, "run", side_effect=fallo):
                self.assertFalse(mr.ya_revisado("o/r", 7, self.B1, self.C1))

    def main(self, entorno, previo, respuestas=None):
        evento = json.dumps({"pull_request": {
            "number": 7, "base": {"sha": "b1"}, "head": {"sha": "c1"}}})
        variables = {"MISTRAL_API_KEY": "clave", "GITHUB_EVENT_PATH": "evento.json",
                     "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "", "GH_TOKEN": "t",
                     "GITHUB_STEP_SUMMARY": ""}
        variables.update(entorno)
        respuesta = json.dumps({"resumen": "R", "hallazgos": [],
                                "comprobaciones": COMPROBACIONES})
        with mock.patch.dict(os.environ, variables), \
                mock.patch("builtins.open", mock.mock_open(read_data=evento)), \
                mock.patch.object(mr, "ya_revisado", return_value=previo) as historial, \
                mock.patch.object(mr, "obtener_diff", return_value=diff_de("a.py", 2, "x")), \
                mock.patch.object(mr, "obtener_rutas_diff", return_value={"a.py"}), \
                mock.patch.object(mr, "leer_guia", return_value=(None, "")), \
                mock.patch.object(mr, "obtener_contexto", return_value=""), \
                mock.patch.object(mr, "llamar_mistral",
                                  side_effect=respuestas or [respuesta]) as api, \
                mock.patch.object(mr, "publicar") as publicar, \
                mock.patch("builtins.print") as salida:
            codigo = mr.main()
        return codigo, historial, api, publicar, salida

    def test_mismo_commit_ya_revisado_no_gasta_api_ni_comenta(self):
        codigo, historial, api, publicar, salida = self.main({"GITHUB_RUN_ATTEMPT": "1"}, True)
        self.assertEqual(codigo, 0)
        historial.assert_called_once_with("o/r", 7, "b1", "c1")
        api.assert_not_called()
        publicar.assert_not_called()
        self.assertIn("no repetida", salida.call_args.args[0])

    def test_sin_informe_previo_revisa_y_deja_la_marca(self):
        codigo, _, api, publicar, _ = self.main({"GITHUB_RUN_ATTEMPT": "1"}, False)
        self.assertEqual(codigo, 0)
        api.assert_called_once()
        self.assertIn(mr.MARCA_OK % ("b1", "c1"), publicar.call_args.args[2])

    def test_reejecutar_a_mano_siempre_revisa(self):
        _, historial, api, publicar, _ = self.main({"GITHUB_RUN_ATTEMPT": "2"}, True)
        historial.assert_not_called()
        api.assert_called_once()
        publicar.assert_called_once()

    def test_sin_token_no_consulta_el_historial(self):
        _, historial, api, _, _ = self.main({"GH_TOKEN": ""}, True)
        historial.assert_not_called()
        api.assert_called_once()


class TestReintentoYCorte(unittest.TestCase):
    """Igualado con los otros repos el 2026-11-13: una respuesta mal formada
    invalidaba la revisión entera (PR #200), y un corte no decía su causa."""

    main = TestNoRepetir.main
    VALIDA = json.dumps({"resumen": "R", "hallazgos": [],
                         "comprobaciones": COMPROBACIONES})
    ROTA = json.dumps({"resumen": "R", "hallazgos": [],
                       "comprobaciones": [{"archivo": "a.py"}]})

    def test_respuesta_mal_formada_se_pide_otra_vez(self):
        codigo, _, api, publicar, salida = self.main(
            {"GH_TOKEN": ""}, False, [self.ROTA, self.VALIDA])
        self.assertEqual(codigo, 0)
        self.assertEqual(api.call_count, 2)
        self.assertIn(mr.MARCA_OK % ("b1", "c1"), publicar.call_args.args[2])
        avisos = [c.args[0] for c in salida.call_args_list if "rechazada" in c.args[0]]
        self.assertEqual(len(avisos), 1)
        self.assertTrue(avisos[0].startswith("::warning::"))
        self.assertIn("solicitud 1 de 2", avisos[0])

    def test_dos_respuestas_mal_formadas_fallan_sin_tercera(self):
        codigo, _, api, publicar, salida = self.main(
            {"GH_TOKEN": ""}, False, [self.ROTA, self.ROTA, self.VALIDA])
        self.assertEqual(codigo, 1)
        self.assertEqual(api.call_count, mr.INTENTOS_RESPUESTA)
        cuerpo = publicar.call_args.args[2]
        self.assertIn("Revisión no válida", cuerpo)
        self.assertNotIn("mistral-review-ok", cuerpo)
        self.assertTrue(any(c.args[0].startswith("::error::")
                            for c in salida.call_args_list))

    def test_corte_de_la_api_nombra_la_causa_y_no_reintenta(self):
        codigo, _, api, publicar, _ = self.main(
            {"GH_TOKEN": ""}, False, [mr.RespuestaIncompleta("length"), self.VALIDA])
        self.assertEqual(codigo, 1)
        api.assert_called_once()
        self.assertIn("incompleta o no válida (`length`)", publicar.call_args.args[2])

    def test_la_causa_se_reduce_a_letras(self):
        fallo = mr.RespuestaIncompleta("Length`\n## titulo <b>" + "x" * 50)
        self.assertRegex(fallo.causa, r"^[a-z_]{1,20}$")
        self.assertEqual(mr.RespuestaIncompleta(None).causa, "")

    def test_otro_valueerror_no_inventa_causa(self):
        _, _, _, publicar, _ = self.main(
            {"GH_TOKEN": ""}, False, [ValueError("vacío")])
        cuerpo = publicar.call_args.args[2]
        self.assertIn("incompleta o no válida. ", cuerpo)
        self.assertNotIn("válida (`", cuerpo)

    def test_margen_de_salida_enviado(self):
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = json.dumps({"choices": [
            {"message": {"content": "{}"}, "finish_reason": "length"}]}).encode()
        with mock.patch.object(mr.urllib.request, "urlopen", return_value=resp) as abrir:
            with self.assertRaises(mr.RespuestaIncompleta) as fallo:
                mr.llamar_mistral([], "m", "clave")
        self.assertEqual(fallo.exception.causa, "length")
        enviado = json.loads(abrir.call_args.args[0].data)
        self.assertEqual(enviado["max_tokens"], mr.MAX_SALIDA)
        self.assertEqual(mr.MAX_SALIDA, 8000)


if __name__ == "__main__":
    unittest.main()
