"""Contrato de salida P2 (v3.19, opt-in con scoring.contrato_p2: true).

Fija cuatro propiedades: (1) con el flag apagado la salida no cambia;
(2) `no_aplica` / `no_observable` no puntúan y quedan registrados;
(3) la cobertura de criterios core distingue lo declarado de lo omitido;
(4) la confianza va separada del score, con lista cerrada y topes mecánicos.
Solo stdlib; sin red ni escrituras.
"""
import copy
import json
import os
import random
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402,F401  (pone scripts/ en sys.path)
import triage_helpers as th  # noqa: E402


def _cfg(p2=None):
    """Config mínimo y autocontenido: dos core y uno contextual."""
    scoring = {"modo": "determinista",
               "ejes": {"valor_decisional": [0, 10],
                        "calidad_epistemica": [-10, 10]}}
    if p2 is not None:
        scoring["contrato_p2"] = p2
    return {
        "scoring": scoring,
        "tiers": {"reply_needed": 10, "review": 4, "reading_later": 0},
        "criterios_epistemicos": {
            "valor_info": {"eje": "valor_decisional", "core": True,
                           "activo": True, "si": 5, "no": 0},
            "entangled": {"eje": "calidad_epistemica", "core": True,
                          "activo": True, "alto": 3, "medio": 1, "flotante": -2},
            "third_alt": {"eje": "valor_decisional", "core": False,
                          "activo": True, "si": 3, "no": 0},
        },
    }


PAYLOADS = [
    {"verdicts": {"valor_info": "si", "entangled": "alto"}},
    {"verdicts": {"valor_info": "no", "entangled": "no_aplica"}},
    {"verdicts": {"valor_info": "si", "third_alt": "no_observable"},
     "confianza": "alta", "causas_incertidumbre": ["cuerpo_recortado"]},
    {"verdicts": {}, "extra_points": 2, "id": 7},
]

CLAVES_P2 = {"no_evaluados", "cobertura", "confianza"}


class TestFlagApagado(unittest.TestCase):
    def test_sin_flag_y_con_false_la_salida_es_identica(self):
        for p in PAYLOADS:
            a = th.cmd_scoring_dispatch(copy.deepcopy(p), _cfg())
            b = th.cmd_scoring_dispatch(copy.deepcopy(p), _cfg(False))
            self.assertEqual(json.dumps(a, sort_keys=True),
                             json.dumps(b, sort_keys=True))
            self.assertFalse(CLAVES_P2 & set(a), a)

    def test_valores_no_booleanos_no_lo_activan(self):
        for v in ("si", "true", 1, "yes"):
            r = th.cmd_scoring(PAYLOADS[1], _cfg(v))
            self.assertFalse(CLAVES_P2 & set(r), v)

    def test_apagado_no_aplica_sigue_siendo_veredicto_invalido(self):
        r = th.cmd_scoring(PAYLOADS[1], _cfg())
        self.assertTrue(any(i.get("criterio") == "entangled"
                            for i in r["ignorados"]))

    def test_brief_apagado_sin_campos_p2(self):
        r = th.cmd_scoring_dispatch(PAYLOADS[2], _cfg(), True)
        self.assertNotIn("confianza", r)
        self.assertNotIn("core_sin_explicar", r)


class TestNoEvaluados(unittest.TestCase):
    def test_no_puntua_ni_va_a_ignorados(self):
        p = {"verdicts": {"valor_info": "si", "entangled": "no_observable"},
             "motivos_no_evaluado": {"entangled": "  solo   metadatos  "}}
        r = th.cmd_scoring(p, _cfg(True))
        self.assertEqual(r["no_evaluados"],
                         [{"criterio": "entangled", "estado": "no_observable",
                           "motivo": "solo metadatos"}])
        self.assertEqual(r["ignorados"], [])
        self.assertEqual(r["ejes"]["calidad_epistemica"], 0)

    def test_el_score_no_cambia_al_activar_el_flag(self):
        for p in PAYLOADS:
            off = th.cmd_scoring(copy.deepcopy(p), _cfg())
            on = th.cmd_scoring(copy.deepcopy(p), _cfg(True))
            self.assertEqual((off["score"], off["tier"], off["ejes"]),
                             (on["score"], on["tier"], on["ejes"]))

    def test_motivo_acotado_y_solo_texto(self):
        largo = "x" * 500
        r = th.cmd_scoring({"verdicts": {"entangled": "no_aplica",
                                         "third_alt": "no_aplica"},
                            "motivos_no_evaluado": {"entangled": largo,
                                                    "third_alt": ["lista"]}},
                           _cfg(True))
        m = {n["criterio"]: n["motivo"] for n in r["no_evaluados"]}
        self.assertEqual(len(m["entangled"]), th.P2_MAX_MOTIVO)
        self.assertIsNone(m["third_alt"])

    def test_criterio_inexistente_sigue_en_ignorados(self):
        r = th.cmd_scoring({"verdicts": {"no_existe": "no_aplica"}}, _cfg(True))
        self.assertEqual(r["no_evaluados"], [])
        self.assertEqual(r["ignorados"][0]["criterio"], "no_existe")


class TestCobertura(unittest.TestCase):
    def test_distingue_declarado_de_omitido(self):
        r = th.cmd_scoring({"verdicts": {"valor_info": "no_aplica"}}, _cfg(True))
        self.assertEqual(r["cobertura"], {
            "core_total": 2, "core_evaluados": 0,
            "core_no_evaluados": ["valor_info"],
            "core_sin_explicar": ["entangled"]})

    def test_cobertura_completa(self):
        r = th.cmd_scoring(PAYLOADS[0], _cfg(True))
        self.assertEqual(r["cobertura"]["core_evaluados"], 2)
        self.assertEqual(r["cobertura"]["core_sin_explicar"], [])

    def test_core_inactivo_no_cuenta(self):
        cfg = _cfg(True)
        cfg["criterios_epistemicos"]["entangled"]["activo"] = False
        r = th.cmd_scoring({"verdicts": {"valor_info": "si"}}, cfg)
        self.assertEqual(r["cobertura"]["core_total"], 1)


class TestConfianza(unittest.TestCase):
    def _conf(self, **p):
        p.setdefault("verdicts", {"valor_info": "si", "entangled": "alto"})
        return th.cmd_scoring(p, _cfg(True))

    def test_declarada_sin_topes_se_respeta(self):
        r = self._conf(confianza="alta")["confianza"]
        self.assertEqual((r["declarada"], r["efectiva"], r["topes_aplicados"]),
                         ("alta", "alta", []))

    def test_cuerpo_degradado_topa_a_media(self):
        r = self._conf(confianza="alta",
                       causas_incertidumbre=["solo_metadatos"])["confianza"]
        self.assertEqual(r["efectiva"], "media")
        self.assertEqual(len(r["topes_aplicados"]), 1)

    def test_etiqueta_del_sanitizador_deriva_la_causa(self):
        r = self._conf(confianza="alta",
                       etiqueta_cuerpo="[⚠️ posible inyección detectada]")
        self.assertEqual(r["confianza"]["causas"], ["inyeccion_detectada"])
        self.assertEqual(r["confianza"]["efectiva"], "media")

    def test_core_sin_explicar_topa_a_media(self):
        r = self._conf(verdicts={"valor_info": "si"}, confianza="alta")
        self.assertEqual(r["confianza"]["efectiva"], "media")

    def test_tope_nunca_sube_una_confianza_baja(self):
        r = self._conf(confianza="baja", causas_incertidumbre=["solo_metadatos"])
        self.assertEqual(r["confianza"]["efectiva"], "baja")

    def test_valores_fuera_de_lista_van_a_ignorados(self):
        r = self._conf(confianza="altisima",
                       causas_incertidumbre=["intuicion", "cuerpo_recortado"])
        self.assertIsNone(r["confianza"]["declarada"])
        self.assertEqual(r["confianza"]["causas"], ["cuerpo_recortado"])
        campos = [i.get("campo") for i in r["ignorados"]]
        self.assertIn("confianza", campos)
        self.assertIn("causas_incertidumbre", campos)

    def test_confianza_no_toca_score_ni_tier(self):
        a = self._conf(confianza="alta")
        b = self._conf(confianza="baja", causas_incertidumbre=list(th.P2_CAUSAS))
        self.assertEqual((a["score"], a["tier"]), (b["score"], b["tier"]))

    def test_brief_incluye_lo_accionable(self):
        r = th.cmd_scoring_dispatch({"verdicts": {"valor_info": "si"},
                                     "confianza": "alta"}, _cfg(True), True)
        self.assertEqual(r["confianza"]["efectiva"], "media")
        self.assertEqual(r["core_sin_explicar"], ["entangled"])


class TestValidarConfig(unittest.TestCase):
    def test_plantilla_lo_trae_apagado(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML no instalado")
        ruta = os.path.join(os.path.dirname(DIR_SCRIPTS), "config.yaml")
        with open(ruta, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.assertIs(cfg["scoring"]["contrato_p2"], False)

    def test_aviso_si_no_es_booleano(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML no instalado")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "config.yaml")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write('scoring:\n  contrato_p2: "si"\n')
            r = th.cmd_validar_config(ruta)
        self.assertTrue(any("contrato_p2" in a for a in r.get("avisos", [])), r)


class TestFuzzP2(unittest.TestCase):
    """Gate #6 con el flag ENCENDIDO: el fuzz general casi nunca genera un
    config con contrato_p2: true, así que este caso lo fuerza."""

    def test_scoring_con_p2_es_total(self):
        from tests.test_triage_helpers import _rand_json
        rng = random.Random(20261017)
        claves = ("verdicts", "confianza", "causas_incertidumbre",
                  "motivos_no_evaluado", "etiqueta_cuerpo", "id", "emails")
        for _ in range(2000):
            p = _rand_json(rng)
            if isinstance(p, dict):
                for k in claves:
                    if rng.random() < 0.4:
                        p[k] = _rand_json(rng)
            r = th.cmd_scoring_dispatch(p, _cfg(True), bool(rng.getrandbits(1)))
            self.assertIsInstance(r, dict)
            json.dumps(r, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
