"""Par `no` (0 puntos) / `__no_aplica__` en la comparación por criterio (v3.22.21).

Medición real 2026-10-27 (3 × 20 llamadas a gpt-6-luna): en los criterios
cuyo «no» vale 0 el modelo alterna entre `no` y `__no_aplica__` con el mismo
correo. Para el score es lo mismo; aquí se fija que la comparación lo cuenta
aparte (`equivalentes`) sin cambiar `coinciden`/`difieren`/`tasa_coincidencia`.
Sin red: transporte simulado.
"""
import os
import unittest
from unittest.mock import patch

from tests.test_jev import lote, respuesta as respuesta_jev
from tests.test_decisions import ACTIVO
import clasificadores as nc
import jev as j
import triage_helpers as th
from tests.test_esquema import _cfg_plantilla


def _v(verdicts=None, no_aplica=(), inciertos=()):
    return {"verdicts": dict(verdicts or {}), "no_aplica": list(no_aplica),
            "inciertos": list(inciertos)}


class TestUnitario(unittest.TestCase):
    def setUp(self):
        self.cfg = _cfg_plantilla()

    def test_no_de_cero_frente_a_no_aplica_es_equivalente_en_ambos_sentidos(self):
        for pri, ext in ((_v({"third_alternative": "no"}), _v(no_aplica=["third_alternative"])),
                         (_v(no_aplica=["third_alternative"]), _v({"third_alternative": "no"}))):
            pc = nc._por_criterio(pri, ext, self.cfg)
            self.assertIn("third_alternative", pc["difieren"])       # significado de siempre
            self.assertIn("third_alternative", pc["equivalentes"])
            self.assertEqual(pc["coinciden"], 0)
            self.assertEqual(pc["coinciden_equivalentes"], 1)

    def test_si_frente_a_no_aplica_no_es_equivalente(self):
        pc = nc._por_criterio(_v({"third_alternative": "si"}),
                              _v(no_aplica=["third_alternative"]), self.cfg)
        self.assertEqual(pc["equivalentes"], {})
        self.assertEqual(pc["coinciden_equivalentes"], 0)

    def test_otras_opciones_de_cero_no_cuentan(self):
        # Variante estricta: `neutral` vale 0 pero no significa «no aplica».
        self.assertEqual(self.cfg["criterios_epistemicos"]["proper_humility"]["neutral"], 0)
        pc = nc._por_criterio(_v({"proper_humility": "neutral"}),
                              _v(no_aplica=["proper_humility"]), self.cfg)
        self.assertEqual(pc["equivalentes"], {})

    def test_no_que_puntua_no_es_equivalente(self):
        # `cambia_algo_concreto: no` vale -5: excluirlo sí cambia el score.
        pc = nc._por_criterio(_v({"cambia_algo_concreto": "no"}),
                              _v(no_aplica=["cambia_algo_concreto"]), self.cfg)
        self.assertEqual(pc["equivalentes"], {})

    def test_excluir_y_no_de_cero_dan_el_mismo_score(self):
        # La premisa de la equivalencia, comprobada con el scoring real.
        base = {"hard_rules": [], "extra_points": 0, "forzar_reply_needed": False,
                "tier_maximo": None, "remitente_en_historial": False, "id": "1"}
        vs = {k: sorted(o)[0] for k, (o, _) in nc.modelos._criterios(self.cfg).items()}
        vs["third_alternative"] = "no"
        sin = {k: x for k, x in vs.items() if k != "third_alternative"}
        a = th.cmd_scoring_dispatch(dict(base, verdicts=vs), self.cfg)
        b = th.cmd_scoring_dispatch(dict(base, verdicts=sin), self.cfg)
        self.assertEqual((a["score"], a["tier"]), (b["score"], b["tier"]))

    def test_sin_cfg_no_hay_equivalencias(self):
        pc = nc._por_criterio(_v({"third_alternative": "no"}), _v(no_aplica=["third_alternative"]))
        self.assertEqual(pc["equivalentes"], {})


class TestIntegracionJev(unittest.TestCase):
    def test_agregado_trae_tasa_equivalente_sin_tocar_la_clasica(self):
        def no_aplica_en_third(body, *_):
            r = respuesta_jev(body)
            for k, a in r["answers"].items():
                elegida = (nc.NO_APLICA if k == "third_alternative" else
                           sorted(o for o in a["probabilities"]
                                  if o not in (nc.INCIERTO, nc.NO_APLICA))[0])
                a.update(choice=elegida,
                         probabilities={o: float(o == elegida) for o in a["probabilities"]})
            return r
        p, cfg = lote(1)
        # El principal de `lote` elige la primera opción en orden: «no».
        self.assertEqual(p["emails"][0]["principal"]["verdicts"]["third_alternative"], "no")
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ficticia"}):
            r = j.comparar(p, cfg, ACTIVO, no_aplica_en_third)
        pc = r["resultados"][0]["por_criterio"]
        self.assertEqual(list(pc["equivalentes"]), ["third_alternative"])
        agg = r["comparacion_por_criterio"]
        n = agg["criterios_comparados"]
        self.assertEqual(agg["tasa_coincidencia"], round((n - 1) / n, 4))
        self.assertEqual(agg["tasa_coincidencia_equivalente"], 1.0)
        self.assertEqual(agg["por_criterio"]["third_alternative"]["equivalentes"], 1)


if __name__ == "__main__":
    unittest.main()
