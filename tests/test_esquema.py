"""Esquema JSON portable del evaluador nativo (`esquema.py`).

Sin red ni modelos: respuestas sintéticas. Prueban el contrato mecánico entre
el esquema y `modelos.validar`, no la calidad de ningún proveedor.
"""
import copy
import json
from pathlib import Path
import random
import unittest

from tests import DIR_SCRIPTS
from tests.test_modelos import lote
from tests.test_triage_helpers import _rand_json
import esquema as es
import jev
import modelos as m
import triage_helpers as th

SKILL = Path(DIR_SCRIPTS).parent
REFERENCIA = SKILL / "references" / "esquema-evaluador.json"


def _cfg_plantilla():
    return th._cargar_config(str(SKILL / "config.yaml"))


def _texto_esquema(cfg):
    # Idéntico a lo que imprime `esquema.py generar` (print añade el salto).
    return json.dumps(es.generar(cfg), ensure_ascii=False, indent=2) + "\n"


class TestReferencia(unittest.TestCase):
    def test_referencia_coincide_byte_a_byte(self):
        # Patrón del gate de es.yaml: si cambia config.yaml o esquema.py,
        # regenera con `esquema.py generar --config config.yaml`.
        self.assertEqual(
            REFERENCIA.read_bytes(),
            _texto_esquema(_cfg_plantilla()).encode("utf-8"),
            "esquema-evaluador.json desactualizado: regenéralo")


_PERMITIDAS = {"type", "properties", "required", "additionalProperties",
               "enum", "items", "description"}
_TIPOS = {"object", "array", "string", "boolean", "null"}


def _fila_esquema(esq):
    return esq["properties"]["evaluaciones"]["items"]["properties"]


def _respuesta_esquema(cfg, excluir=None):
    """Respuesta sintética en forma «esquema»: todas las claves, null donde
    no aplica. `excluir` (no core) va en no_aplica en vez de en verdicts."""
    vs, na, ev = {}, {}, {}
    for k, (opciones, _) in m._criterios(cfg).items():
        if k == excluir:
            vs[k], na[k], ev[k] = None, "No procede en este correo.", None
        else:
            vs[k], na[k], ev[k] = sorted(opciones)[0], None, "Evidencia sintética."
    return {"evaluaciones": [{"id": "1", "verdicts": vs, "no_aplica": na,
                              "evidencias": ev, "dudas": [],
                              "resumen": "Resumen sintético.", "eco": None}]}


def _validar(cfg, respuesta_validador):
    p = lote()
    p["config"] = cfg
    p["respuesta"] = respuesta_validador
    return m.ejecutar("validar", p)


class TestForma(unittest.TestCase):
    def setUp(self):
        self.cfg = _cfg_plantilla()
        self.activos = m._criterios(self.cfg)
        self.fila = _fila_esquema(es.generar(self.cfg))

    def test_cada_criterio_activo_con_sus_opciones_y_ninguno_de_mas(self):
        for campo in ("verdicts", "no_aplica", "evidencias"):
            self.assertEqual(set(self.fila[campo]["properties"]), set(self.activos))
        for k, (opciones, _) in self.activos.items():
            enum = self.fila["verdicts"]["properties"][k]["enum"]
            self.assertEqual(set(enum), opciones | {None})
            self.assertEqual(len(enum), len(opciones) + 1)

    def test_core_no_admite_no_aplica(self):
        for k, (_, core) in self.activos.items():
            tipo = self.fila["no_aplica"]["properties"][k]["type"]
            self.assertEqual(tipo, "null" if core else ["string", "null"], k)

    def test_subconjunto_comun_y_modo_estricto(self):
        def recorrer(nodo, ruta):
            self.assertLessEqual(set(nodo), _PERMITIDAS, ruta)
            tipos = nodo["type"] if isinstance(nodo["type"], list) else [nodo["type"]]
            self.assertLessEqual(set(tipos), _TIPOS, ruta)
            if isinstance(nodo["type"], list):
                # Anulable solo como [X, "null"].
                self.assertEqual(len(tipos), 2, ruta)
                self.assertEqual(tipos[1], "null", ruta)
            if "properties" in nodo:
                self.assertEqual(set(nodo["required"]), set(nodo["properties"]), ruta)
                self.assertIs(nodo["additionalProperties"], False, ruta)
                for k, sub in nodo["properties"].items():
                    recorrer(sub, ruta + "." + k)
            if "items" in nodo:
                recorrer(nodo["items"], ruta + "[]")
        recorrer(es.generar(self.cfg), "$")

    def test_capa_veloz_solo_core(self):
        cfg = th._fusiona_config_veloz(
            _cfg_plantilla(), str(SKILL / "config-veloz.yaml"))
        fila = _fila_esquema(es.generar(cfg))
        core = {k for k, (_, c) in self.activos.items() if c}
        self.assertTrue(core)
        self.assertEqual(set(fila["verdicts"]["properties"]), core)


class TestIdaYVuelta(unittest.TestCase):
    def setUp(self):
        self.cfg = _cfg_plantilla()
        self.no_core = next(k for k, (_, c) in m._criterios(self.cfg).items() if not c)

    def _ciclo(self, respuesta):
        c = es.comprobar(self.cfg, respuesta)
        self.assertTrue(c["ok"], c)
        return c, _validar(self.cfg, c["normalizada"])

    def test_respuesta_conforme_la_acepta_validar(self):
        for excluir in (None, self.no_core):
            c, r = self._ciclo(_respuesta_esquema(self.cfg, excluir))
            self.assertTrue(c["conforme"], c["errores"])
            self.assertTrue(r["ok"], r)
            for fila in r["resultados"]:
                self.assertIn(fila["motivo"],
                              ("propuesta_valida", "reevaluar_tier_o_umbral"))

    def test_lo_que_el_esquema_no_cubre_lo_rechaza_validar(self):
        k = self.no_core
        casos = {
            "evidencias_ausentes": lambda f: f["evidencias"].update({k: None}),
            # Veredicto y no_aplica a la vez.
            "cobertura_incompleta_o_desconocida":
                lambda f: f["no_aplica"].update({k: "Razón."}),
        }
        for motivo, mutar in casos.items():
            resp = _respuesta_esquema(self.cfg)
            mutar(resp["evaluaciones"][0])
            c, r = self._ciclo(resp)
            self.assertTrue(c["conforme"], c["errores"])
            self.assertEqual(r["resultados"][0]["motivo"], motivo)
        # Ambos null: el criterio desaparece de la cobertura.
        resp = _respuesta_esquema(self.cfg)
        f = resp["evaluaciones"][0]
        f["verdicts"][k] = f["evidencias"][k] = None
        c, r = self._ciclo(resp)
        self.assertTrue(c["conforme"], c["errores"])
        self.assertEqual(r["resultados"][0]["motivo"],
                         "cobertura_incompleta_o_desconocida")

    def test_no_conforme_se_informa_sin_valores(self):
        resp = _respuesta_esquema(self.cfg)
        resp["evaluaciones"][0]["verdicts"]["cambia_algo_concreto"] = "SECRETO_DEL_CORREO"
        resp["evaluaciones"][0]["intruso"] = "SECRETO_DEL_CORREO"
        c = es.comprobar(self.cfg, resp)
        self.assertFalse(c["conforme"])
        self.assertNotIn("SECRETO", json.dumps(c["errores"]))

    def test_normalizar_no_toca_valores(self):
        resp = _respuesta_esquema(self.cfg, self.no_core)
        original = copy.deepcopy(resp)
        n = es.normalizar(resp)["respuesta"]["evaluaciones"][0]
        self.assertEqual(resp, original)  # pura: no muta la entrada
        self.assertNotIn("eco", n)
        self.assertNotIn(self.no_core, n["verdicts"])
        self.assertEqual(n["no_aplica"], {self.no_core: "No procede en este correo."})


class TestTotalidad(unittest.TestCase):
    def test_normalizar_nunca_lanza(self):
        rng = random.Random(20261027)
        for _ in range(3000):
            entrada = _rand_json(rng)
            if rng.random() < 0.5:
                entrada = {"evaluaciones": [_rand_json(rng) for _ in range(3)]}
            r = es.normalizar(entrada)
            self.assertIsInstance(r, dict)
            json.dumps(r)


class TestJsonschema(unittest.TestCase):
    def test_validador_externo_si_esta_instalado(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema no instalado (opcional)")
        cfg = _cfg_plantilla()
        esq = es.generar(cfg)
        jsonschema.Draft202012Validator.check_schema(esq)
        jsonschema.validate(_respuesta_esquema(cfg), esq)


class TestSincroniaJev(unittest.TestCase):
    def test_mismas_opciones_y_mismos_core(self):
        cfg = _cfg_plantilla()
        activos = m._criterios(cfg)
        preguntas = jev._preguntas(cfg, activos)
        fila = _fila_esquema(es.generar(cfg))
        especiales = {"__incierto__", "__no_aplica__"}
        self.assertEqual(set(preguntas), set(fila["verdicts"]["properties"]))
        for k, q in preguntas.items():
            enum = set(fila["verdicts"]["properties"][k]["enum"]) - {None}
            self.assertEqual(enum, set(q["criteria"]) - especiales, k)
        sin_no_aplica = {k for k, q in preguntas.items()
                         if "__no_aplica__" not in q["criteria"]}
        nulos = {k for k, v in fila["no_aplica"]["properties"].items()
                 if v["type"] == "null"}
        self.assertEqual(sin_no_aplica, nulos)


if __name__ == "__main__":
    unittest.main()
