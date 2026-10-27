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

    def test_no_neutro_frente_a_no_aplica_se_pliega(self):
        k = "third_alternative"
        tiradas = iter([_api(self._variante(k, "no")),
                        _api(_respuesta_esquema(self.cfg, excluir=k))])
        r = mr.medir(self.cfg, mr.CORREOS[:1], 2, lambda c: next(tiradas))
        self.assertIn(k, r["criterios_inestables"])
        self.assertNotIn(k, r["criterios_inestables_equivalentes"])

    def test_si_frente_a_no_aplica_no_se_pliega(self):
        k = "third_alternative"
        tiradas = iter([_api(self._variante(k, "si")),
                        _api(_respuesta_esquema(self.cfg, excluir=k))])
        r = mr.medir(self.cfg, mr.CORREOS[:1], 2, lambda c: next(tiradas))
        self.assertIn(k, r["criterios_inestables_equivalentes"])

    def test_tier_estable_con_respuestas_identicas(self):
        r = mr.medir(self.cfg, mr.CORREOS[:1], 3, lambda c: _api(self.base))
        v = r["por_correo"]["logistica"]
        self.assertEqual(sum(v["tiers"].values()), 3)
        self.assertEqual(len(v["tiers"]), 1)
        self.assertEqual(v["score_min"], v["score_max"])
        self.assertEqual(r["correos_tier_inestable"], [])

    def test_tier_usa_el_scoring_real(self):
        # Misma cuenta que el plugin: nada calculado aparte.
        r = mr.medir(self.cfg, mr.CORREOS[:1], 2, lambda c: _api(self.base))
        v, _ = mr.veredictos(self.cfg, _api(self.base))
        score, tier = mr.score_tier(self.cfg, v)
        self.assertEqual(r["por_correo"]["logistica"],
                         {"tiers": {tier: 2}, "score_min": score, "score_max": score,
                          "margen": min(abs(score - u) for u in mr.umbrales(self.cfg))})

    def test_umbrales_sin_reply_needed_con_el_tope_activo(self):
        # Con el tope por defecto, REPLY_NEEDED no depende del score.
        cfg = {"tiers": {"reply_needed": 10, "review": 4, "reading_later": 0}}
        self.assertEqual(sorted(mr.umbrales(cfg)), [0, 4])
        cfg["scoring"] = {"cap_reply_needed_sin_accion": False}
        self.assertEqual(sorted(mr.umbrales(cfg)), [0, 4, 10])

    def test_score_alto_sin_accion_no_llega_a_reply_needed(self):
        # La premisa de `umbrales`, comprobada con el scoring real.
        vs = {k: max(o, key=lambda x: self.cfg["criterios_epistemicos"][k].get(x, 0)
                     if isinstance(self.cfg["criterios_epistemicos"][k].get(x), (int, float)) else -99)
              for k, (o, _) in mr.nc.modelos._criterios(self.cfg).items()}
        score, tier = mr.score_tier(self.cfg, vs)
        self.assertGreaterEqual(score, self.cfg["tiers"]["reply_needed"])
        self.assertEqual(tier, "REVIEW")

    def test_no_neutro_y_no_aplica_dan_el_mismo_tier(self):
        k = "third_alternative"
        a, _ = mr.veredictos(self.cfg, _api(self._variante(k, "no")))
        b, _ = mr.veredictos(self.cfg, _api(_respuesta_esquema(self.cfg, excluir=k)))
        self.assertEqual(mr.score_tier(self.cfg, a), mr.score_tier(self.cfg, b))

    def test_cambio_de_tier_se_detecta(self):
        k = "cambia_algo_concreto"  # su `no` vale -5: mueve el score
        tiradas = iter([_api(self._variante(k, "si")), _api(self._variante(k, "no"))])
        a, _ = mr.veredictos(self.cfg, _api(self._variante(k, "si")))
        b, _ = mr.veredictos(self.cfg, _api(self._variante(k, "no")))
        r = mr.medir(self.cfg, mr.CORREOS[:1], 2, lambda c: next(tiradas))
        v = r["por_correo"]["logistica"]
        self.assertNotEqual(v["score_min"], v["score_max"])
        distintos = mr.score_tier(self.cfg, a)[1] != mr.score_tier(self.cfg, b)[1]
        self.assertEqual(r["correos_tier_inestable"] == ["logistica"], distintos)

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
        self.assertIn("Contando `no` (0 puntos) = `__no_aplica__`: 30 de 30.", texto)
        self.assertIn("Correos con el mismo tier en todas las tiradas: 1 de 1.", texto)
        self.assertIn("Margen al umbral", texto)


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

    def test_ids_repetidos_se_rechazan_antes_de_llamar(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            json.dump([{"id": "a", "texto": "x"}, {"id": "a", "texto": "y"}], f)
        self.addCleanup(os.unlink, f.name)
        # Sin --ejecutar: sin el freno imprimiría el plan y saldría con 0.
        argv = ["medir_ruido.py", "--modelo", "m", "--correos", f.name]
        with mock.patch.object(mr, "transporte_http") as t, \
                mock.patch.object(sys, "argv", argv), \
                redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()), \
                self.assertRaises(SystemExit):
            mr.main()
        t.assert_not_called()


class TestTransporte(unittest.TestCase):
    def test_tiempo_agotado_es_error_contable(self):
        import urllib.error
        for exc in (TimeoutError("t"), urllib.error.URLError("caida")):
            with mock.patch("urllib.request.urlopen", side_effect=exc):
                r = mr.transporte_http({}, "k", timeout=1)
            self.assertEqual(mr.veredictos({}, r), (None, "error_api"))


if __name__ == "__main__":
    unittest.main()
