"""Evaluación del revisor de Mistral con casos reales (2026-11-13).

Sin red ni API: fijan la parte mecánica de `.github/scripts/mistral_eval.py`
(qué objetivo se deriva de un arreglo, dónde cae un hallazgo, qué se cuenta).
Que el modelo acierte no se puede probar aquí: es lo que la evaluación mide.
"""
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "mistral_eval", os.path.join(_RAIZ, ".github", "scripts", "mistral_eval.py"))
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)
mr = ev.mr

SHA = "a" * 40
POSITIVO = {"id": "p", "tipo": "positivo", "base": SHA, "cabeza": SHA,
            "arreglo": SHA, "defecto": "d"}
NEGATIVO = {"id": "n", "tipo": "negativo", "base": SHA, "cabeza": SHA,
            "archivos": ["a.py"], "defecto": "d"}

DIFF = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,3 +1,4 @@
 def f(x):
+    y = x + 1
     return x

"""


class TestCasos(unittest.TestCase):
    def cargar(self, casos):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(casos, fh)
        try:
            return ev.cargar_casos(fh.name)
        finally:
            os.unlink(fh.name)

    def test_acepta_los_dos_tipos(self):
        self.assertEqual(len(self.cargar([POSITIVO, NEGATIVO])), 2)

    def test_rechaza_casos_incompletos_repetidos_o_sin_sha(self):
        malos = ([dict(POSITIVO, tipo="otro")],
                 [{k: v for k, v in POSITIVO.items() if k != "arreglo"}],
                 [{k: v for k, v in NEGATIVO.items() if k != "archivos"}],
                 [dict(POSITIVO, cabeza="HEAD; rm -rf /")],
                 [dict(POSITIVO, cabeza=SHA + "; rm -rf /")],
                 [dict(POSITIVO, cabeza=SHA + "\n")],
                 [dict(POSITIVO, cabeza=SHA[:7])],
                 [dict(NEGATIVO, archivos="scripts/a.py")],
                 [dict(NEGATIVO, archivos=["scripts/a.py", 3])],
                 [dict(POSITIVO, ignorar="scripts/a.py")],
                 [POSITIVO, dict(POSITIVO)])
        for casos in malos:
            with self.subTest(casos=casos), self.assertRaises(ValueError):
                self.cargar(casos)

    def test_el_fichero_del_repo_es_valido_y_fija_commits_completos(self):
        casos = ev.cargar_casos(ev.CASOS)
        self.assertTrue(any(c["tipo"] == "positivo" for c in casos))
        self.assertTrue(any(c["tipo"] == "negativo" for c in casos))
        for c in casos:
            for clave in ("base", "cabeza", "arreglo"):
                if clave in c:
                    self.assertRegex(c[clave], r"^[0-9a-f]{40}$")


class TestObjetivos(unittest.TestCase):
    def test_el_objetivo_es_la_funcion_que_el_arreglo_toco(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                return subprocess.run(["git", "-C", d] + list(a), check=True,
                                      capture_output=True, text=True).stdout.strip()

            def escribir(nombre, texto):
                os.makedirs(os.path.dirname(os.path.join(d, nombre)) or d, exist_ok=True)
                with open(os.path.join(d, nombre), "w") as fh:
                    fh.write(texto)

            git("init", "-q")
            git("config", "user.email", "t@t"); git("config", "user.name", "t")
            codigo = ("def sana(x):\n    return x\n\n\n"
                      "def rota(x):\n    y = x\n    return y - 1\n")
            escribir("a.py", codigo)
            escribir("tests/test_a.py", "def test_a():\n    pass\n")
            escribir("otro.py", "V = 1\n")
            git("add", "-A"); git("commit", "-qm", "defecto")
            cabeza = git("rev-parse", "HEAD")
            escribir("a.py", codigo.replace("y - 1", "y + 1"))
            escribir("tests/test_a.py", "def test_a():\n    assert True\n")
            escribir("otro.py", "V = 2\n")
            git("commit", "-qam", "arreglo")
            caso = dict(POSITIVO, cabeza=cabeza, arreglo=git("rev-parse", "HEAD"),
                        ignorar=["otro.py"])
            viejo = os.getcwd()
            try:
                os.chdir(d)
                destino = ev.objetivos(caso)
            finally:
                os.chdir(viejo)
        self.assertEqual(destino, {"a.py": [(5, 7, "rota")]})   # ni tests ni ignorados

    def test_negativo_apunta_a_sus_archivos(self):
        self.assertEqual(ev.objetivos(NEGATIVO), {"a.py": []})


class TestRangosObjetivo(unittest.TestCase):
    """El objetivo no es el contexto: una vecina sin tocar no cuenta (Codex, PR #203)."""

    FUENTE = (
        "def antes():\n"        # 1
        "    return 1\n"        # 2
        "\n"                    # 3
        "MARCA = 'x'\n"         # 4
        "OTRA = 'y'\n"          # 5
        "\n"                    # 6
        "def despues():\n"      # 7
        "    return 2\n"        # 8
    )

    def test_un_cambio_de_modulo_no_arrastra_las_funciones_vecinas(self):
        rangos = ev._rangos_objetivo(self.FUENTE, {4, 5})
        self.assertEqual(rangos, [(4, 5, "")])
        # El contexto del revisor sí las abarca: por eso no sirve de objetivo.
        contexto = mr._rangos_python(self.FUENTE, {4, 5})
        self.assertTrue(any(i <= 2 <= f for i, f, _ in contexto))

    def test_una_linea_de_modulo_pegada_a_una_funcion_no_se_une_a_ella(self):
        fuente = "X = 1\ndef f():\n    return X\n"
        self.assertEqual(ev._rangos_objetivo(fuente, {1, 3}),
                         [(1, 1, ""), (2, 3, "f")])

    def test_fuente_que_no_parsea_no_da_objetivos(self):
        self.assertEqual(ev._rangos_objetivo("def (:\n", {1}), [])


class TestClasificar(unittest.TestCase):
    def test_lineas_citadas_son_las_de_la_cabeza(self):
        self.assertEqual(ev.lineas_citadas(DIFF, "a.py", "y = x + 1"), {2})
        self.assertEqual(ev.lineas_citadas(DIFF, "a.py", "+    y = x + 1\nreturn x"), {2, 3})
        self.assertEqual(ev.lineas_citadas(DIFF, "b.py", "y = x + 1"), set())
        self.assertEqual(ev.lineas_citadas(DIFF, "a.py", "}"), set())

    def test_una_linea_eliminada_cuenta_por_sus_vecinas(self):
        # Quitar una guarda solo se puede citar por la linea borrada (Codex, PR #203).
        diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
                "@@ -1,4 +1,3 @@\n def f(x):\n-    if x is None: return 0\n"
                "     return x + 1\n \n")
        self.assertEqual(ev.lineas_citadas(diff, "a.py", "if x is None: return 0"), {1, 2})
        hallazgo = {"archivo": "a.py", "fragmento": "-    if x is None: return 0"}
        self.assertTrue(mr.cita_en(hallazgo["fragmento"], mr.indice_diff(diff)["a.py"]))
        self.assertEqual(ev.clasificar(hallazgo, diff, {"a.py": [(1, 2, "f")]}), "funcion")

    def test_funcion_archivo_o_fuera(self):
        def h(archivo, fragmento):
            return {"archivo": archivo, "fragmento": fragmento}
        destino = {"a.py": [(1, 2, "f")]}
        self.assertEqual(ev.clasificar(h("a.py", "y = x + 1"), DIFF, destino), "funcion")
        self.assertEqual(ev.clasificar(h("a.py", "return x"), DIFF, destino), "archivo")
        self.assertEqual(ev.clasificar(h("b.py", "y = x + 1"), DIFF, destino), "fuera")
        # Negativo: sin rangos, el archivo entero cuenta como «archivo».
        self.assertEqual(ev.clasificar(h("a.py", "y = x + 1"), DIFF, {"a.py": []}), "archivo")


COMPROBACIONES = [{"archivo": "a.py", "escenario": "e", "conclusion": "c",
                   "estado": "pendiente"}]
HALLAZGO = {"severidad": "media", "archivo": "a.py", "fragmento": "y = x + 1",
            "problema": "p", "escenario": "e", "arreglo": "a"}


class TestRevisar(unittest.TestCase):
    def revisar(self, respuestas, destino=None):
        with mock.patch.object(mr, "obtener_diff", return_value=DIFF), \
                mock.patch.object(mr, "obtener_rutas_diff", return_value={"a.py"}), \
                mock.patch.object(mr, "obtener_contexto", return_value=""), \
                mock.patch.object(mr, "leer_guia", return_value=(None, "")), \
                mock.patch.object(ev, "git", return_value="asunto\n"), \
                mock.patch.object(ev, "objetivos",
                                  return_value=destino or {"a.py": [(1, 2, "f")]}), \
                mock.patch.object(mr, "llamar_mistral", side_effect=respuestas) as api:
            return ev.revisar(POSITIVO, "m", "clave"), api

    def test_revision_valida_clasifica_hallazgos_y_pendientes(self):
        texto = json.dumps({"resumen": "R", "hallazgos": [HALLAZGO],
                            "comprobaciones": COMPROBACIONES})
        registro, api = self.revisar([texto])
        self.assertEqual(registro["estado"], "valida")
        self.assertEqual(registro["solicitudes"], 1)
        self.assertEqual(registro["hallazgos"][0], dict(HALLAZGO, donde="funcion"))
        self.assertEqual(registro["pendientes"][0], {
            "archivo": "a.py", "escenario": "e", "conclusion": "c", "donde": "archivo"})
        # El asunto del commit es el titulo; no hay descripcion que delate el arreglo.
        usuario = api.call_args.args[0][1]["content"]
        self.assertIn("asunto", usuario)
        self.assertIn("(sin descripción)", usuario)

    def test_respuesta_mal_formada_se_pide_dos_veces_y_queda_invalida(self):
        registro, api = self.revisar(["no json", "no json", "no json"])
        self.assertEqual((registro["estado"], api.call_count), ("invalida", 2))
        self.assertEqual(registro["hallazgos"], [])

    def test_el_registro_conserva_el_hallazgo_entero_para_etiquetarlo(self):
        largo = dict(HALLAZGO, problema="p" * 900, escenario="entrada " + "e" * 900,
                     arreglo="a" * 900)
        texto = json.dumps({"resumen": "R", "hallazgos": [largo],
                            "comprobaciones": COMPROBACIONES})
        registro, _ = self.revisar([texto])
        for campo in ("problema", "escenario", "arreglo", "fragmento"):
            self.assertEqual(registro["hallazgos"][0][campo], largo[campo])

    def test_corte_y_error_de_api_se_registran_sin_reintentar(self):
        registro, api = self.revisar([mr.RespuestaIncompleta("length")])
        self.assertEqual((registro["estado"], registro["detalle"]), ("cortada", "length"))
        api.assert_called_once()
        fallo = mr.urllib.error.HTTPError(mr.API, 500, "e", {}, io.BytesIO(b""))
        registro, _ = self.revisar([fallo])
        self.assertEqual((registro["estado"], registro["detalle"]), ("error", "HTTP 500"))


class TestPresupuesto(unittest.TestCase):
    def test_cuenta_peticiones_http_reales_y_corta_en_el_transporte(self):
        fallo = mr.urllib.error.HTTPError(mr.API, 503, "e", {}, io.BytesIO(b""))
        original = mr.urllib.request.urlopen
        with mock.patch.object(mr.urllib.request, "urlopen", side_effect=fallo) as abrir, \
                mock.patch.object(mr.time, "sleep"):
            with ev.Presupuesto(4) as presupuesto:
                # Una llamada con errores transitorios son tres peticiones, no una.
                with self.assertRaises(mr.urllib.error.HTTPError):
                    mr.llamar_mistral([], "m", "clave")
                self.assertEqual(presupuesto.usadas, 3)
                with self.assertRaises(ev.PresupuestoAgotado):
                    mr.llamar_mistral([], "m", "clave")
                self.assertEqual((presupuesto.usadas, abrir.call_count), (4, 4))
            self.assertIs(mr.urllib.request.urlopen, abrir)   # se restaura al salir
        self.assertIs(mr.urllib.request.urlopen, original)

    def respuesta(self, cuerpo):
        r = mock.MagicMock()
        r.__enter__.return_value = r
        r.read.return_value = json.dumps(cuerpo).encode("utf-8")
        return r

    def test_suma_los_tokens_que_declara_la_api(self):
        buena = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                 "usage": {"prompt_tokens": 30000, "completion_tokens": 9000}}
        sin_uso = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                   "usage": {"prompt_tokens": "muchos", "completion_tokens": True}}
        with mock.patch.object(mr.urllib.request, "urlopen", side_effect=[
                self.respuesta(buena), self.respuesta(buena), self.respuesta(sin_uso)]):
            with ev.Presupuesto(5) as presupuesto:
                for _ in range(3):
                    self.assertEqual(mr.llamar_mistral([], "m", "clave"), "{}")
        self.assertEqual((presupuesto.entrada, presupuesto.salida), (60000, 18000))
        self.assertEqual((presupuesto.respondidas, presupuesto.sin_esfuerzo), (2, 0))

    def test_avisa_si_el_modelo_no_admite_el_esfuerzo(self):
        rechazo = mr.urllib.error.HTTPError(
            mr.API, 400, "e", {}, io.BytesIO(b"reasoning_effort is not supported"))
        buena = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        with mock.patch.object(mr.urllib.request, "urlopen",
                               side_effect=[rechazo, self.respuesta(buena)]):
            with ev.Presupuesto(5) as presupuesto:
                mr.llamar_mistral([], "m", "clave")
        self.assertEqual((presupuesto.usadas, presupuesto.sin_esfuerzo), (2, 1))

    def test_agotado_deja_informe_parcial_y_falla(self):
        salida = io.StringIO()
        registro = {"estado": "valida", "detalle": "", "solicitudes": 0,
                    "recortado": False, "hallazgos": [], "pendientes": []}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "clave"}), \
                mock.patch.object(ev, "cargar_casos", return_value=[POSITIVO, NEGATIVO]), \
                mock.patch.object(ev, "revisar",
                                  side_effect=[registro, ev.PresupuestoAgotado()]), \
                mock.patch.object(mr, "escribir_resumen"), redirect_stdout(salida):
            ruta = os.path.join(d, "r.json")
            codigo = ev.main(["--ejecutar", "--repeticiones", "1", "--salida", ruta])
            with open(ruta, encoding="utf-8") as fh:
                guardado = json.load(fh)
        self.assertEqual(codigo, 1)
        self.assertTrue(guardado["incompleta"])
        self.assertEqual((len(guardado["resultados"]["p"]), guardado["resultados"]["n"]),
                         (1, []))
        self.assertIn("Evaluación incompleta", salida.getvalue())


class TestInforme(unittest.TestCase):
    def test_cuenta_lo_que_senala_la_funcion_y_lista_para_etiquetar(self):
        def r(estado, donde=None):
            return {"estado": estado, "detalle": "length" if estado == "cortada" else "",
                    "solicitudes": 1, "recortado": False, "pendientes": [],
                    "hallazgos": [{"severidad": "alta", "archivo": "a.py",
                                   "problema": "texto del hallazgo", "fragmento": "x",
                                   "escenario": "entrada concreta", "arreglo": "a",
                                   "donde": donde}]
                    if donde else []}
        resultados = {"p": [r("valida", "funcion"), r("cortada")],
                      "n": [r("valida", "archivo"), r("valida")]}
        informe = ev.resumir([POSITIVO, NEGATIVO], resultados, "m", 2)
        self.assertIn("**Revisiones válidas:** 3 de 4 (cortada: 1)", informe)
        self.assertIn("en 1 de 1 casos", informe)
        self.assertIn("en 1 de 1 revisiones válidas", informe)
        self.assertIn("1 hallazgo(s) en 2 revisiones válidas; 1 en los mismos archivos",
                      informe)
        self.assertIn("| `p` | positivo | 1/2 | 1/1 | 1 | 0 |", informe)
        self.assertIn("| `n` | negativo | 2/2 | — | 1 | 0 |", informe)
        self.assertIn("hallazgo alta [funcion] en `a.py`: texto del hallazgo", informe)
        self.assertIn("  - Escenario: entrada concreta", informe)
        self.assertIn("Repetición 2: cortada (length).", informe)
        self.assertIn("Repetición 2: sin hallazgos ni pendientes.", informe)


class TestMain(unittest.TestCase):
    def main(self, argv, entorno=None):
        salida = io.StringIO()
        with mock.patch.dict(os.environ, entorno or {"MISTRAL_API_KEY": ""}), \
                mock.patch.object(ev, "cargar_casos", return_value=[POSITIVO, NEGATIVO]), \
                mock.patch.object(ev, "listar", return_value="lista"), \
                mock.patch.object(ev, "revisar") as revisar, \
                mock.patch.object(mr, "escribir_resumen"), redirect_stdout(salida):
            revisar.return_value = {"estado": "valida", "detalle": "", "solicitudes": 1,
                                    "recortado": False, "hallazgos": [], "pendientes": []}
            codigo = ev.main(argv)
        return codigo, revisar, salida.getvalue()

    def test_sin_ejecutar_solo_lista_y_no_llama(self):
        codigo, revisar, salida = self.main([])
        self.assertEqual((codigo, salida.strip()), (0, "lista"))
        revisar.assert_not_called()

    def test_sin_clave_no_evalua_y_falla(self):
        codigo, revisar, salida = self.main(["--ejecutar"])
        self.assertEqual(codigo, 2)
        revisar.assert_not_called()
        self.assertIn("MISTRAL_API_KEY", salida)

    def test_tope_de_solicitudes_y_casos_desconocidos(self):
        con_clave = {"MISTRAL_API_KEY": "clave"}
        codigo, revisar, _ = self.main(["--ejecutar", "--repeticiones", "500"], con_clave)
        self.assertEqual(codigo, 2)
        revisar.assert_not_called()
        codigo, revisar, _ = self.main(["--ejecutar", "--solo", "no-existe"], con_clave)
        self.assertEqual(codigo, 2)
        revisar.assert_not_called()

    def test_ejecuta_cada_caso_las_veces_pedidas_y_guarda_el_json(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "r.json")
            codigo, revisar, salida = self.main(
                ["--ejecutar", "--solo", "p", "--repeticiones", "3", "--salida", ruta],
                {"MISTRAL_API_KEY": "clave", "MISTRAL_MODEL": "modelo-x"})
            with open(ruta, encoding="utf-8") as fh:
                guardado = json.load(fh)
        self.assertEqual((codigo, revisar.call_count), (0, 3))
        self.assertEqual(guardado["modelo"], "modelo-x")
        self.assertEqual(len(guardado["resultados"]["p"]), 3)
        self.assertNotIn("clave", json.dumps(guardado))
        self.assertIn("Evaluación del revisor de Mistral (`modelo-x`", salida)

    def test_modelo_y_esfuerzo_solo_para_la_evaluacion(self):
        vistos = []
        con_clave = {"MISTRAL_API_KEY": "clave", "MISTRAL_MODEL": "modelo-x"}
        previo = mr.ESFUERZO
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "r.json")
            salida = io.StringIO()
            registro = {"estado": "valida", "detalle": "", "solicitudes": 1,
                        "recortado": False, "hallazgos": [], "pendientes": []}
            with mock.patch.dict(os.environ, con_clave), \
                    mock.patch.object(ev, "cargar_casos", return_value=[POSITIVO]), \
                    mock.patch.object(ev, "revisar", side_effect=lambda c, m, k: (
                        vistos.append((m, mr.ESFUERZO)), dict(registro))[1]), \
                    mock.patch.object(mr, "escribir_resumen"), redirect_stdout(salida):
                codigo = ev.main(["--ejecutar", "--repeticiones", "1", "--salida", ruta,
                                  "--modelo", "mistral-large-2512", "--esfuerzo", "high"])
            with open(ruta, encoding="utf-8") as fh:
                guardado = json.load(fh)
        self.assertEqual(codigo, 0)
        self.assertEqual(vistos, [("mistral-large-2512", "high")])
        self.assertEqual(mr.ESFUERZO, previo)          # se restaura al acabar
        self.assertEqual((guardado["modelo"], guardado["esfuerzo"]),
                         ("mistral-large-2512", "high"))
        self.assertEqual(guardado["tokens"]["entrada"], 0)
        self.assertIn("Esfuerzo de razonamiento pedido: `high`", salida.getvalue())

    def test_vacios_usan_la_variable_y_el_esfuerzo_del_revisor(self):
        codigo, revisar, salida = self.main(
            ["--ejecutar", "--solo", "p", "--repeticiones", "1",
             "--modelo", "", "--esfuerzo", ""],
            {"MISTRAL_API_KEY": "clave", "MISTRAL_MODEL": "modelo-x"})
        self.assertEqual(codigo, 0)
        self.assertEqual(revisar.call_args.args[1], "modelo-x")
        self.assertIn("pedido: `%s`" % mr.ESFUERZO, salida)

    def test_rechaza_modelo_o_esfuerzo_raros_sin_llamar(self):
        con_clave = {"MISTRAL_API_KEY": "clave"}
        for extra in (["--modelo", "m\"; rm -rf /"], ["--modelo", "a b"],
                      ["--modelo", "x" * 81], ["--esfuerzo", "máximo"]):
            with self.subTest(extra=extra):
                codigo, revisar, _ = self.main(["--ejecutar"] + extra, con_clave)
                self.assertEqual(codigo, 2)
                revisar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
