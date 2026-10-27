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
import clasificadores as nc
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


_PERMITIDAS, _TIPOS = es._PALABRAS, es._TIPOS


def _fila_esquema(esq):
    return esq["properties"]["evaluaciones"]["items"]["properties"]


def _crit_esquema(esq):
    return _fila_esquema(esq)["criterios"]["properties"]


def _respuesta_esquema(cfg, excluir=None):
    """Respuesta sintética en forma «esquema»: un objeto por criterio con
    todas sus claves. `excluir` (no core) va como `__no_aplica__`."""
    crit = {}
    for k, (opciones, core) in m._criterios(cfg).items():
        if k == excluir:
            c = {"veredicto": es.NO_APLICA, "evidencia": "",
                 "razon_no_aplica": "No procede en este correo."}
        else:
            c = {"veredicto": sorted(opciones)[0], "evidencia": "Evidencia sintética."}
            if not core:
                c["razon_no_aplica"] = ""
        crit[k] = c
    return {"evaluaciones": [{"id": "1", "criterios": crit, "dudas": [],
                              "resumen": "Resumen sintético.",
                              "eco": {"inicio": "", "fin": ""}}]}


def _validar(cfg, respuesta_validador):
    p = lote()
    p["config"] = cfg
    p["respuesta"] = respuesta_validador
    return m.ejecutar("validar", p)


def _uniones(nodo):
    """Parámetros con tipo unión (lista en `type`), lo que limita Anthropic."""
    n = isinstance(nodo.get("type"), list)
    n += sum(_uniones(v) for v in nodo.get("properties", {}).values())
    return n + (_uniones(nodo["items"]) if "items" in nodo else 0)


class TestForma(unittest.TestCase):
    def setUp(self):
        self.cfg = _cfg_plantilla()
        self.activos = m._criterios(self.cfg)
        self.crit = _crit_esquema(es.generar(self.cfg))

    def test_cada_criterio_activo_con_sus_opciones_y_ninguno_de_mas(self):
        self.assertEqual(set(self.crit), set(self.activos))
        for k, (opciones, core) in self.activos.items():
            enum = self.crit[k]["properties"]["veredicto"]["enum"]
            extra = set() if core else {es.NO_APLICA}
            self.assertEqual(set(enum), opciones | extra, k)
            self.assertEqual(len(enum), len(set(enum)), k)

    def test_core_no_admite_no_aplica(self):
        for k, (_, core) in self.activos.items():
            campos = set(self.crit[k]["properties"])
            enum = self.crit[k]["properties"]["veredicto"]["enum"]
            if core:
                self.assertEqual(campos, {"veredicto", "evidencia"}, k)
                self.assertNotIn(es.NO_APLICA, enum, k)
            else:
                self.assertEqual(campos, {"veredicto", "evidencia", "razon_no_aplica"}, k)

    def test_subconjunto_comun_y_modo_estricto(self):
        def recorrer(nodo, ruta):
            self.assertLessEqual(set(nodo), _PERMITIDAS, ruta)
            # Sin uniones: ni [X, "null"] (revisión Codex, PR #135).
            self.assertIsInstance(nodo["type"], str, ruta)
            self.assertIn(nodo["type"], _TIPOS, ruta)
            if "properties" in nodo:
                self.assertEqual(set(nodo["required"]), set(nodo["properties"]), ruta)
                self.assertIs(nodo["additionalProperties"], False, ruta)
                for k, sub in nodo["properties"].items():
                    recorrer(sub, ruta + "." + k)
            if "items" in nodo:
                recorrer(nodo["items"], ruta + "[]")
        recorrer(es.generar(self.cfg), "$")

    def test_limite_de_uniones_de_anthropic(self):
        veloz = th._fusiona_config_veloz(
            _cfg_plantilla(), str(SKILL / "config-veloz.yaml"))
        for cfg in (self.cfg, veloz):
            self.assertLessEqual(_uniones(es.generar(cfg)), 16)

    def test_capa_veloz_solo_core(self):
        cfg = th._fusiona_config_veloz(
            _cfg_plantilla(), str(SKILL / "config-veloz.yaml"))
        core = {k for k, (_, c) in self.activos.items() if c}
        self.assertTrue(core)
        self.assertEqual(set(_crit_esquema(es.generar(cfg))), core)


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
        # Conformes con el esquema pero inválidos para el contrato.
        casos = [
            ("evidencias_ausentes", None, {"evidencia": ""}),
            ("criterio_core_omitido_o_sin_justificacion", k,
             {"razon_no_aplica": ""}),
        ]
        for motivo, excluir, cambio in casos:
            resp = _respuesta_esquema(self.cfg, excluir)
            resp["evaluaciones"][0]["criterios"][k].update(cambio)
            c, r = self._ciclo(resp)
            self.assertTrue(c["conforme"], c["errores"])
            self.assertEqual(r["resultados"][0]["motivo"], motivo)

    def test_lo_que_el_esquema_ya_impide(self):
        # Excluir un core, u omitir un criterio, ya no es conforme.
        for mutar in (
                lambda c: c["cambia_algo_concreto"].update(veredicto=es.NO_APLICA),
                lambda c: c.pop(self.no_core)):
            resp = _respuesta_esquema(self.cfg)
            mutar(resp["evaluaciones"][0]["criterios"])
            self.assertFalse(es.comprobar(self.cfg, resp)["conforme"])

    def test_no_conforme_se_informa_sin_valores(self):
        resp = _respuesta_esquema(self.cfg)
        f = resp["evaluaciones"][0]
        f["criterios"]["cambia_algo_concreto"]["veredicto"] = "SECRETO_DEL_CORREO"
        f["intruso"] = "SECRETO_DEL_CORREO"
        c = es.comprobar(self.cfg, resp)
        self.assertFalse(c["conforme"])
        self.assertNotIn("SECRETO", json.dumps(c["errores"]))

    def test_normalizar_reparte_sin_tocar_valores(self):
        resp = _respuesta_esquema(self.cfg, self.no_core)
        original = copy.deepcopy(resp)
        n = es.normalizar(resp)["respuesta"]["evaluaciones"][0]
        self.assertEqual(resp, original)  # pura: no muta la entrada
        self.assertNotIn("criterios", n)
        self.assertEqual(n["eco"], {"inicio": "", "fin": ""})
        self.assertNotIn(self.no_core, n["verdicts"])
        self.assertNotIn(self.no_core, n["evidencias"])
        self.assertEqual(n["no_aplica"], {self.no_core: "No procede en este correo."})
        self.assertEqual(n["evidencias"]["cambia_algo_concreto"], "Evidencia sintética.")


class TestConfigRota(unittest.TestCase):
    def test_config_no_objeto_da_error_json(self):
        import subprocess, sys, tempfile
        for contenido in ("", "null\n", "- a\n"):
            with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
                f.write(contenido)
                f.flush()
                for cmd in ("generar", "comprobar"):
                    r = subprocess.run(
                        [sys.executable, str(Path(DIR_SCRIPTS) / "esquema.py"),
                         cmd, "--config", f.name],
                        input="{}", capture_output=True, text=True)
                    self.assertEqual(r.returncode, 1, (contenido, cmd))
                    self.assertEqual(json.loads(r.stdout)["motivo"],
                                     "entrada_o_config_invalida")
                    self.assertNotIn("Traceback", r.stderr)


class TestTotalidad(unittest.TestCase):
    def test_normalizar_nunca_lanza(self):
        rng = random.Random(20261027)
        for _ in range(3000):
            entrada = _rand_json(rng)
            t = rng.random()
            if t < 0.3:
                entrada = {"evaluaciones": [_rand_json(rng) for _ in range(3)]}
            elif t < 0.6:
                entrada = {"evaluaciones": [{"criterios": {
                    "a": _rand_json(rng), "b": {"veredicto": _rand_json(rng)}}}]}
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
        crit = _crit_esquema(es.generar(cfg))
        self.assertEqual(es.NO_APLICA, nc.NO_APLICA)
        especiales = {nc.INCIERTO, nc.NO_APLICA}
        self.assertEqual(set(preguntas), set(crit))
        for k, q in preguntas.items():
            enum = set(crit[k]["properties"]["veredicto"]["enum"])
            self.assertEqual(enum - especiales, set(q["criteria"]) - especiales, k)
        sin_no_aplica = {k for k, q in preguntas.items()
                         if nc.NO_APLICA not in q["criteria"]}
        sin_exclusion = {k for k, v in crit.items()
                         if es.NO_APLICA not in v["properties"]["veredicto"]["enum"]}
        self.assertEqual(sin_no_aplica, sin_exclusion)


if __name__ == "__main__":
    unittest.main()
