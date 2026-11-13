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


class TestClasificar(unittest.TestCase):
    def test_lineas_citadas_son_las_de_la_cabeza(self):
        self.assertEqual(ev.lineas_citadas(DIFF, "a.py", "y = x + 1"), {2})
        self.assertEqual(ev.lineas_citadas(DIFF, "a.py", "+    y = x + 1\nreturn x"), {2, 3})
        self.assertEqual(ev.lineas_citadas(DIFF, "b.py", "y = x + 1"), set())
        self.assertEqual(ev.lineas_citadas(DIFF, "a.py", "}"), set())

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
        self.assertEqual(registro["hallazgos"][0]["donde"], "funcion")
        self.assertEqual(registro["pendientes"][0]["donde"], "archivo")
        # El asunto del commit es el titulo; no hay descripcion que delate el arreglo.
        usuario = api.call_args.args[0][1]["content"]
        self.assertIn("asunto", usuario)
        self.assertIn("(sin descripción)", usuario)

    def test_respuesta_mal_formada_se_pide_dos_veces_y_queda_invalida(self):
        registro, api = self.revisar(["no json", "no json", "no json"])
        self.assertEqual((registro["estado"], api.call_count), ("invalida", 2))
        self.assertEqual(registro["hallazgos"], [])

    def test_corte_y_error_de_api_se_registran_sin_reintentar(self):
        registro, api = self.revisar([mr.RespuestaIncompleta("length")])
        self.assertEqual((registro["estado"], registro["detalle"]), ("cortada", "length"))
        api.assert_called_once()
        fallo = mr.urllib.error.HTTPError(mr.API, 500, "e", {}, io.BytesIO(b""))
        registro, _ = self.revisar([fallo])
        self.assertEqual((registro["estado"], registro["detalle"]), ("error", "HTTP 500"))


class TestInforme(unittest.TestCase):
    def test_cuenta_lo_que_senala_la_funcion_y_lista_para_etiquetar(self):
        def r(estado, donde=None):
            return {"estado": estado, "detalle": "length" if estado == "cortada" else "",
                    "solicitudes": 1, "recortado": False, "pendientes": [],
                    "hallazgos": [{"severidad": "alta", "archivo": "a.py",
                                   "problema": "texto del hallazgo", "donde": donde}]
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


if __name__ == "__main__":
    unittest.main()
