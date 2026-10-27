"""`scripts/medir_ruido.py`: agregación del ruido entre ejecuciones.

Sin red: el transporte se sustituye por respuestas sintéticas con la forma
de Chat Completions. Prueban el recuento, no la calidad de ningún modelo.
"""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(_RAIZ, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(_RAIZ, "scripts"))

from tests import DIR_SCRIPTS  # noqa: E402,F401  (pone la skill en sys.path)
from tests.test_esquema import _cfg_plantilla, _respuesta_esquema  # noqa: E402
import medir_ruido as mr  # noqa: E402


def _api(contenido):
    return {"choices": [{"message": {"content": json.dumps(contenido)}}]}


class TestMedir(unittest.TestCase):
    def setUp(self):
        self.cfg = _cfg_plantilla()
        self.base = _respuesta_esquema(self.cfg)

    def _variante(self, criterio, valor):
        r = json.loads(json.dumps(self.base))
        r["evaluaciones"][0]["criterios"][criterio]["veredicto"] = valor
        return r

    def test_respuestas_identicas_no_dan_inestables(self):
        r = mr.medir(self.cfg, mr.CORREOS[:2], 3, lambda c: _api(self.base))
        self.assertEqual(r["criterios_inestables"], [])
        self.assertEqual(r["fallos"], {})
        self.assertEqual(r["correos_comparables"], 2)

    def test_detecta_el_criterio_que_cambia(self):
        k = "retorno_atencional"
        opciones = ("alto", "bajo")
        tiradas = iter([_api(self._variante(k, opciones[0])),
                        _api(self._variante(k, opciones[1])),
                        _api(self._variante(k, opciones[0]))])
        r = mr.medir(self.cfg, mr.CORREOS[:1], 3, lambda c: next(tiradas))
        self.assertEqual(r["criterios_inestables"], [k])
        self.assertEqual(r["por_criterio"][k]["valores"]["logistica"],
                         {"alto": 2, "bajo": 1})

    def test_no_aplica_cuenta_como_valor(self):
        k = "retorno_atencional"
        excluido = _respuesta_esquema(self.cfg, excluir=k)
        tiradas = iter([_api(self.base), _api(excluido)])
        r = mr.medir(self.cfg, mr.CORREOS[:1], 2, lambda c: next(tiradas))
        self.assertIn(k, r["criterios_inestables"])
        self.assertIn(mr.NO_APLICA, r["por_criterio"][k]["valores"]["logistica"])

    def test_fallos_cuentan_aparte_y_no_se_rellenan(self):
        malas = iter([{"error": {"message": "x"}},
                      {"choices": [{"message": {"refusal": "no"}}]},
                      _api({"evaluaciones": []}),
                      {"choices": [{"message": {"content": "no es json"}}]}])
        r = mr.medir(self.cfg, mr.CORREOS[:1], 4, lambda c: next(malas))
        self.assertEqual(r["fallos"], {"error_api": 1, "rechazo": 1,
                                       "filas_inesperadas": 1, "forma_inesperada": 1})
        self.assertEqual(r["tiradas_validas"], {"logistica": 0})
        self.assertEqual(r["correos_comparables"], 0)
        self.assertEqual(r["criterios_inestables"], [])

    def test_respuesta_no_conforme_es_fallo(self):
        mal = self._variante("cambia_algo_concreto", "VALOR_INVENTADO")
        r = mr.medir(self.cfg, mr.CORREOS[:1], 2, lambda c: _api(mal))
        self.assertEqual(r["fallos"], {"no_conforme": 2})

    def test_peticion_usa_modo_estricto_y_el_correo(self):
        cuerpo = mr.peticion({"type": "object"}, "m", mr.CORREOS[0])
        js = cuerpo["response_format"]["json_schema"]
        self.assertIs(js["strict"], True)
        self.assertIn("La reunión del jueves", cuerpo["messages"][0]["content"])

    def test_perfil_va_antes_del_correo_y_es_opcional(self):
        sin = mr.peticion({}, "m", mr.CORREOS[0])["messages"][0]["content"]
        con = mr.peticion({}, "m", mr.CORREOS[0], "Psicólogo")["messages"][0]["content"]
        self.assertNotIn("perfil_minimo", sin)
        self.assertTrue(con.endswith(sin))
        self.assertIn("perfil_minimo: Psicólogo", con)

    def test_markdown_resume(self):
        r = mr.medir(self.cfg, mr.CORREOS[:1], 2, lambda c: _api(self.base))
        texto = mr.markdown(r)
        self.assertIn("Criterios estables en todos los correos: 30 de 30.", texto)


class TestSinEjecutarNoHayRed(unittest.TestCase):
    def test_plan_por_defecto_no_llama(self):
        with mock.patch.object(mr, "transporte_http") as t, \
                mock.patch.object(sys, "argv", ["medir_ruido.py", "--modelo", "m"]):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(mr.main(), 0)
        t.assert_not_called()
        plan = json.loads(out.getvalue())["plan"]
        self.assertEqual(plan["llamadas"], len(mr.CORREOS) * 5)
        self.assertFalse(plan["con_perfil"])

    def test_perfil_demasiado_largo_se_rechaza(self):
        argv = ["medir_ruido.py", "--modelo", "m", "--perfil", "x" * (mr.MAX_PERFIL + 1)]
        with mock.patch.object(sys, "argv", argv), \
                redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            mr.main()


if __name__ == "__main__":
    unittest.main()
