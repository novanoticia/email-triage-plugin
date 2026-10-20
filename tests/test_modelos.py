"""Delegación opcional: aislamiento, contratos y regresión de reglas existentes.

No llama proveedores. Las respuestas son sintéticas: estas pruebas demuestran
validación mecánica, no calidad del modelo ni compatibilidad real de un host.
"""
import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import DIR_SCRIPTS
import modelos as m
import triage_helpers as th

SKILL = Path(DIR_SCRIPTS).parent


def plan():
    return {"config": {"modo": "hibrido"}, "host": {
        "proveedor": "anthropic", "modelo_principal": "principal-prueba",
        "modelo_economico": "economico-prueba",
        "modelos": [{"id": "economico-prueba", "proveedor": "anthropic"}],
        **{k: True for k in ("delegacion", "seleccion_modelo", "contexto_aislado",
                             "sin_herramientas", "misma_conexion")}}}


PLAN_OK = {"ok": True, "modo": "hibrido", "delegar": True,
           "modelo_solicitado": "economico-prueba", "proveedor": "anthropic",
           "llamadas_restantes": 2, "tamano_lote": 25, "concurrencia": 1}


def lote():
    cfg = yaml.safe_load((SKILL / "config.yaml").read_text())
    activos = m._criterios(cfg)
    vs = {k: next(iter(opciones)) for k, (opciones, _) in activos.items()}
    return {"plan": PLAN_OK, "config": cfg, "esperados": [{"id": "1", "control": {
        "hard_rules": [], "extra_points": 0, "forzar_reply_needed": False,
        "tier_maximo": None, "remitente_en_historial": False}}],
        "respuesta": {"evaluaciones": [{"id": "1", "verdicts": vs,
            "no_aplica": {}, "evidencias": {k: "Evidencia sintética." for k in vs},
            "dudas": [], "resumen": "Resumen sintético."}]}}


class TestPlan(unittest.TestCase):
    def test_ausente_o_actual_no_delega_ni_necesita_capacidades(self):
        for p in ({}, {"config": {"modo": "actual"}},
                  {"config": yaml.safe_load((SKILL / "config-modelos.yaml").read_text())}):
            self.assertEqual(m.ejecutar("planificar", p),
                             {"ok": True, "modo": "actual", "delegar": False})

    def test_mismo_proveedor_y_presupuesto(self):
        for proveedor in ("anthropic", "openai"):
            p = plan()
            p["host"]["proveedor"] = proveedor
            p["host"]["modelos"][0]["proveedor"] = proveedor
            p["llamadas_realizadas"] = 1
            r = m.ejecutar("planificar", p)
            self.assertTrue(r["delegar"])
            self.assertEqual(r["llamadas_restantes"], 1)
            self.assertEqual(r["concurrencia"], 1)

    def test_capacidades_no_verificadas_o_misma_conexion_desconocida(self):
        for k in ("delegacion", "seleccion_modelo", "contexto_aislado",
                  "sin_herramientas", "misma_conexion"):
            for valor in (False, None, "true", 1):
                p = plan()
                p["host"][k] = valor
                self.assertTrue(m.ejecutar("planificar", p)["usar_principal"])

    def test_otro_proveedor_jev_api_o_modelo_no_expuesto_se_rechazan(self):
        cambios = [({"modo": "externo"}, {}), ({"proveedor": "jev"}, {}),
                   ({"api_key": "no-es-una-clave"}, {}),
                   ({"modelo": "no-existe"}, {}),
                   ({}, {"proveedor": "jev"}),
                   ({}, {"modelos": [{"id": "economico-prueba", "proveedor": "openai"}]}),
                   ({}, {"modelo_principal": "economico-prueba"}),
                   ({}, {"modelo_principal": None})]
        for config, host in cambios:
            p = plan()
            p["config"].update(config)
            p["host"].update(host)
            self.assertFalse(m.ejecutar("planificar", p)["ok"])

    def test_limite_agotado_y_presupuesto_invalido(self):
        p = plan()
        p["llamadas_realizadas"] = 2
        self.assertEqual(m.ejecutar("planificar", p)["motivo"], "presupuesto_agotado")
        for campo in ("max_llamadas", "tamano_lote"):
            for v in (0, -1, True, 1001, "2"):
                p = plan()
                p["config"][campo] = v
                self.assertFalse(m.ejecutar("planificar", p)["ok"])


class TestValidar(unittest.TestCase):
    def setUp(self):
        self.p = lote()
        self.fila = self.p["respuesta"]["evaluaciones"][0]

    def resultado(self):
        r = m.ejecutar("validar", self.p)
        self.assertTrue(r["ok"], r)
        return r["resultados"][0]

    def test_scoring_identico_al_actual_y_sin_mutar_entradas(self):
        antes = copy.deepcopy(self.p)
        r = self.resultado()
        esperado = dict(self.p["esperados"][0]["control"], id="1",
                        verdicts=self.fila["verdicts"])
        self.assertEqual(r["resultado"], th.cmd_scoring_dispatch(esperado, self.p["config"]))
        self.assertEqual(self.p, antes)
        self.assertTrue(r["revision_obligatoria"])

    def test_falta_criterio_core_o_evidencia(self):
        k = next(k for k, (_, core) in m._criterios(self.p["config"]).items() if core)
        del self.fila["verdicts"][k]
        del self.fila["evidencias"][k]
        self.assertTrue(self.resultado()["usar_principal"])
        self.fila["no_aplica"][k] = "No aplicable."
        self.assertTrue(self.resultado()["usar_principal"])

    def test_no_core_se_puede_omitir_con_justificacion(self):
        k = next(k for k, (_, core) in m._criterios(self.p["config"]).items() if not core)
        del self.fila["verdicts"][k]
        del self.fila["evidencias"][k]
        self.fila["no_aplica"][k] = "No hay argumento de ese tipo."
        self.assertIn("resultado", self.resultado())
        self.fila["no_aplica"][k] = ""
        self.assertTrue(self.resultado()["usar_principal"])

    def test_opcion_booleano_o_no_admitida_y_dudas(self):
        k = next(iter(self.fila["verdicts"]))
        for v in (True, None, [], {}, "inexistente"):
            self.fila["verdicts"][k] = v
            self.assertTrue(self.resultado()["usar_principal"])
        self.p = lote()
        self.p["respuesta"]["evaluaciones"][0]["dudas"] = ["Falta contexto del hilo."]
        self.assertTrue(self.resultado()["usar_principal"])

    def test_especialista_no_puede_inyectar_control_o_destinos(self):
        for k, v in (("tier_maximo", None), ("forzar_reply_needed", True),
                     ("score", 100), ("hard_rules", []), ("destino", "Archivo")):
            self.fila[k] = v
            self.assertTrue(self.resultado()["usar_principal"])
            del self.fila[k]

    def test_inyeccion_detectada_regresa_al_principal(self):
        self.p["esperados"][0]["control"].update(tier_maximo="REVIEW", forzar_reply_needed=True)
        r = self.resultado()
        self.assertTrue(r["usar_principal"])
        self.assertNotIn("resultado", r)

    def test_control_incompleto_no_se_rellena_por_defecto(self):
        del self.p["esperados"][0]["control"]["forzar_reply_needed"]
        self.assertEqual(self.resultado()["motivo"], "control_incompleto")

    def test_boost_duplicado_o_desconocido_no_se_suma(self):
        for reglas in (["pregunta_directa_boost"] * 2, ["inexistente"]):
            self.p["esperados"][0]["control"]["hard_rules"] = reglas
            r = self.resultado()
            self.assertTrue(r["usar_principal"])
            self.assertNotIn("resultado", r)

    def test_reply_y_archivo_exigen_reevaluacion(self):
        self.p["esperados"][0]["control"]["forzar_reply_needed"] = True
        r = self.resultado()
        self.assertEqual(r["resultado"]["tier"], "REPLY_NEEDED")
        self.assertTrue(r["usar_principal"])
        self.p["esperados"][0]["control"].update(forzar_reply_needed=False, extra_points=-1000)
        r = self.resultado()
        self.assertEqual(r["resultado"]["tier"], "ARCHIVE")
        self.assertTrue(r["usar_principal"])

    def test_umbral_exige_reevaluacion_y_revision_clara_no_repite(self):
        inicial = self.resultado()["resultado"]["score"]
        for objetivo, reevaluar in ((4, True), (5, True), (6, False), (9, True)):
            self.p["esperados"][0]["control"]["extra_points"] = objetivo - inicial
            r = self.resultado()
            self.assertEqual(r["resultado"]["score"], objetivo)
            self.assertEqual(r["usar_principal"], reevaluar)

    def test_ids_duplicados_y_extranos_rechazan_lote(self):
        self.p["respuesta"]["evaluaciones"].append(copy.deepcopy(self.fila))
        self.assertFalse(m.ejecutar("validar", self.p)["ok"])
        self.p["respuesta"]["evaluaciones"][-1]["id"] = "999"
        self.assertFalse(m.ejecutar("validar", self.p)["ok"])

    def test_respuesta_ausente_no_descarta_otro_correo_valido(self):
        segundo = copy.deepcopy(self.p["esperados"][0])
        segundo["id"] = "2"
        self.p["esperados"].append(segundo)
        r = m.ejecutar("validar", self.p)
        self.assertIn("resultado", r["resultados"][0])
        self.assertEqual(r["resultados"][1]["motivo"], "respuesta_ausente")

    def test_veloz_solo_exige_core_segun_config_real(self):
        self.p["config"] = th._fusiona_config_veloz(self.p["config"], str(SKILL / "config-veloz.yaml"))
        core = m._criterios(self.p["config"])
        for campo in ("verdicts", "evidencias"):
            self.fila[campo] = {k: v for k, v in self.fila[campo].items() if k in core}
        self.assertIn("resultado", self.resultado())
        self.assertEqual(len(core), 13)


class TestComparar(unittest.TestCase):
    def test_desacuerdo_no_es_verdad_y_no_inventa_ahorro(self):
        r = m.ejecutar("comparar", {"plan": PLAN_OK,
                                  "base": [{"id": "1", "tier": "REPLY_NEEDED", "score": 10}],
                                  "propuesta": [{"id": "1", "tier": "ARCHIVE", "score": -2}]})
        self.assertEqual(r["reply_a_archive"], ["1"])
        self.assertEqual(r["diferencias"][0]["delta_score"], -12)
        self.assertEqual(r["referencia"], "modelo_principal_no_verdad")
        self.assertNotIn("ahorro", r)

    def test_no_compara_muestras_distintas_o_incompletas(self):
        b = [{"id": "1", "score": 2, "tier": "READING_LATER"}]
        for a in ([], b * 2, [{"id": "2", "score": 2, "tier": "READING_LATER"}],
                  [{"id": "1", "score": float("nan"), "tier": "REVIEW"}]):
            self.assertFalse(m.ejecutar("comparar", {"plan": PLAN_OK,
                                                     "base": b, "propuesta": a})["ok"])

    def test_sin_plan_que_autorice_no_compara(self):
        b = [{"id": "1", "score": 2, "tier": "READING_LATER"}]
        r = m.ejecutar("comparar", {"base": b, "propuesta": b})
        self.assertEqual(r["motivo"], "delegacion_no_autorizada")
        self.assertTrue(r["usar_principal"])


class TestPlanAutorizaDelegacion(unittest.TestCase):
    """Prueba real (2026-10-19): planificar dijo delegacion_nativa_no_
    verificada, el modelo delegó igualmente y validar aceptó la respuesta."""

    def test_validar_exige_el_plan(self):
        p = lote()
        del p["plan"]
        self.assertEqual(m.ejecutar("validar", p)["motivo"],
                         "delegacion_no_autorizada")

    def test_un_plan_que_dijo_usar_principal_no_autoriza(self):
        cerrado = plan()
        cerrado["host"]["sin_herramientas"] = False
        negativa = m.ejecutar("planificar", cerrado)
        self.assertEqual(negativa["motivo"], "delegacion_nativa_no_verificada")
        actual = m.ejecutar("planificar", {"config": {"modo": "actual"}})
        for p_falso in (negativa, actual, {"ok": True, "delegar": True},
                        {"ok": True, "delegar": "true", "modo": "hibrido"}, None):
            p = lote()
            p["plan"] = p_falso
            r = m.ejecutar("validar", p)
            self.assertFalse(r["ok"], p_falso)
            self.assertEqual(r["motivo"], "delegacion_no_autorizada")

    def test_un_plan_incompleto_o_de_otro_lote_no_autoriza(self):
        # Revisión (Codex P1): basta con tres campos sueltos no debe valer, y
        # un lote mayor que el autorizado tampoco.
        p = lote()
        p["plan"] = {"ok": True, "modo": "hibrido", "delegar": True}
        self.assertEqual(m.ejecutar("validar", p)["motivo"],
                         "delegacion_no_autorizada")
        p = lote()
        p["plan"] = dict(PLAN_OK, llamadas_restantes=0)
        self.assertEqual(m.ejecutar("validar", p)["motivo"],
                         "delegacion_no_autorizada")
        for cambio in ({"proveedor": "jev"}, {"concurrencia": 2},
                       {"concurrencia": True}, {"llamadas_restantes": 1.0}):
            p = lote()
            p["plan"] = dict(PLAN_OK, **cambio)
            self.assertEqual(m.ejecutar("validar", p)["motivo"],
                             "delegacion_no_autorizada", cambio)
        p = lote()
        p["plan"] = dict(PLAN_OK, tamano_lote=1)
        p["esperados"] = p["esperados"] * 2
        p["esperados"][1] = dict(p["esperados"][1], id="2")
        self.assertEqual(m.ejecutar("validar", p)["motivo"],
                         "lote_mayor_que_el_autorizado")

    def test_comparar_admite_la_sesion_de_varios_lotes(self):
        # Revisión (Codex P2): comparar agrega todas las llamadas de la
        # sesión; el tope es tamano_lote × llamadas_restantes, no un lote.
        def filas(n):
            return [{"id": str(i), "score": 1, "tier": "REVIEW"} for i in range(n)]
        plan_ = dict(PLAN_OK, modo="comparar", tamano_lote=2, llamadas_restantes=2)
        r = m.ejecutar("comparar", {"plan": plan_, "base": filas(4),
                                    "propuesta": filas(4)})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["total"], 4)
        r = m.ejecutar("comparar", {"plan": plan_, "base": filas(5),
                                    "propuesta": filas(5)})
        self.assertEqual(r["motivo"], "lote_mayor_que_el_autorizado")

    def test_el_plan_real_de_planificar_si_autoriza(self):
        p = lote()
        p["plan"] = m.ejecutar("planificar", plan())
        self.assertTrue(p["plan"]["delegar"])
        self.assertTrue(m.ejecutar("validar", p)["ok"])


class TestCLIYPaquete(unittest.TestCase):
    def test_json_invalido_no_expone_datos_ni_traceback(self):
        r = subprocess.run([sys.executable, str(SKILL / "scripts/modelos.py"), "validar"],
                           input="dato-privado-invalido", text=True, capture_output=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr, "")
        self.assertNotIn("dato-privado", r.stdout)
        self.assertFalse(json.loads(r.stdout)["ok"])

    def test_cli_lee_config_real_sin_reconstruccion_por_modelo(self):
        p = lote()
        p["config"] = {"criterios_epistemicos": {}}  # --config manda
        r = subprocess.run([sys.executable, str(SKILL / "scripts/modelos.py"), "validar",
                            "--config", str(SKILL / "config.yaml")],
                           input=json.dumps(p), text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("resultado", json.loads(r.stdout)["resultados"][0])

    def test_config_rota_degrada_sin_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.yaml"
            ruta.write_text("a: [")
            r = subprocess.run([sys.executable, str(SKILL / "scripts/modelos.py"), "validar",
                                "--config", str(ruta)], input=json.dumps(lote()),
                               text=True, capture_output=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr, "")
        self.assertTrue(json.loads(r.stdout)["usar_principal"])

    def test_agente_claude_sin_herramientas_y_sin_modelo_fijo(self):
        agent = (SKILL.parent.parent / "agents/evaluador-criterios.md").read_text()
        fm = yaml.safe_load(agent.split("---", 2)[1])
        self.assertEqual(fm["tools"], [])
        self.assertEqual(fm["model"], "inherit")

    def test_entrada_arbitraria_devuelve_json_serializable(self):
        rng = random.Random(42)
        from tests.test_triage_helpers import _rand_json
        for _ in range(1000):
            for cmd in ("planificar", "validar", "comparar"):
                r = m.ejecutar(cmd, _rand_json(rng))
                self.assertIsInstance(r, dict)
                json.dumps(r, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
