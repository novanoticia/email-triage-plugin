"""Aviso de lectura recortada (v3.22.17).

Experimento real (2026-10-27): `sanitizar` entregó 2500 caracteres por
correo y el script propio del modelo (`leer_bloque.py`, `[:N]` con N=900)
los recortó antes de leerlos. Ningún freno lo vio. Con `ancla_extracto` y
`eco_lectura`, `scoring` lo marca e `informe` lo avisa. Solo aviso: no
cambia score ni tier. Sin red; tempfiles.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from tests.test_huellas_plantilla import CFG, evaluacion_honesta
import triage_helpers as th

TEXTO = " ".join("palabra%d" % i for i in range(400))   # ~4000 caracteres


def correo(i, leido, ancla=None, **extra):
    """Payload de un correo cuyo modelo leyó `leido` del extracto."""
    pal = leido.split()
    return dict({"id": "m%d" % i, "verdicts": evaluacion_honesta(1)[0],
                 "ancla_extracto": ancla or th.ancla_extracto(TEXTO),
                 "eco_lectura": {"inicio": " ".join(pal[:6]),
                                 "fin": " ".join(pal[-6:])}}, **extra)


class TestLecturaEnScoring(unittest.TestCase):
    def test_lectura_entera_se_verifica(self):
        r = th.cmd_scoring_dispatch(correo(1, TEXTO), CFG)
        self.assertIs(r["lectura_verificada"], True)
        self.assertNotIn("lectura_recortada", r)

    def test_recorte_a_900_se_marca_y_no_cambia_el_score(self):
        r = th.cmd_scoring_dispatch(correo(1, TEXTO[:900]), CFG)
        self.assertIs(r["lectura_recortada"], True)
        sin = th.cmd_scoring_dispatch(
            {"id": "m1", "verdicts": evaluacion_honesta(1)[0]}, CFG)
        self.assertEqual((r["score"], r["tier"]), (sin["score"], sin["tier"]))

    def test_marca_de_truncado_y_puntuacion_no_dan_falso_aviso(self):
        saneado = TEXTO[:2500] + " [truncado]"
        ancla = th.ancla_extracto(saneado)
        leido = saneado.replace(" [truncado]", "").replace(" ", ", ").upper()
        r = th.cmd_scoring_dispatch(correo(1, leido, ancla), CFG)
        self.assertIs(r.get("lectura_verificada"), True, r)

    def test_sin_campos_nada_cambia(self):
        r = th.cmd_scoring_dispatch(
            {"verdicts": evaluacion_honesta(1)[0]}, CFG)
        self.assertNotIn("lectura_verificada", r)
        self.assertNotIn("lectura_recortada", r)
        self.assertNotIn("eco_lectura",
                         {i.get("campo") for i in r["ignorados"]})

    def test_formas_raras_no_acusan_y_lo_dicen(self):
        for ancla, eco in ((th.ancla_extracto(TEXTO), None),
                           (None, {"inicio": "a", "fin": "b"}),
                           ("texto", {"inicio": "a", "fin": "b"}),
                           ({"inicio": 1, "fin": "x"}, {"inicio": "a", "fin": "b"}),
                           ([], {})):
            p = {"verdicts": evaluacion_honesta(1)[0],
                 "ancla_extracto": ancla, "eco_lectura": eco}
            r = th.cmd_scoring_dispatch(p, CFG)
            json.dumps(r)
            self.assertNotIn("lectura_recortada", r, (ancla, eco))
            self.assertIn("eco_lectura", {i.get("campo") for i in r["ignorados"]})

    def test_lote_alerta_y_brief(self):
        lote = {"emails": [correo(1, TEXTO), correo(2, TEXTO[:900]),
                           correo(3, TEXTO[:700])]}
        out = th.cmd_scoring_dispatch(lote, CFG, brief=True)
        self.assertEqual(out["alerta_lectura"]["ids"], ["m2", "m3"])
        self.assertIs(out["resultados"][0]["lectura_verificada"], True)
        self.assertIs(out["resultados"][1]["lectura_recortada"], True)
        sin = th.cmd_scoring_dispatch({"emails": [correo(1, TEXTO)]}, CFG)
        self.assertNotIn("alerta_lectura", sin)

    def test_extracto_vacio_no_acusa(self):
        ancla = th.ancla_extracto("")
        r = th.cmd_scoring_dispatch(
            {"verdicts": evaluacion_honesta(1)[0], "ancla_extracto": ancla,
             "eco_lectura": {"inicio": "", "fin": ""}}, CFG)
        self.assertIs(r.get("lectura_verificada"), True)


class TestLecturaEnInforme(unittest.TestCase):
    def test_informe_avisa_con_los_numeros(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(th, "base_estado", return_value=d):
            ruta = os.path.join(d, "desgloses", "s1.jsonl")
            lote = {"emails": [correo(1, TEXTO), correo(2, TEXTO[:900])]}
            th.cmd_registrar(ruta, {"ts": "t", "desglose":
                                    th.cmd_scoring_dispatch(lote, CFG)})
            unidades = [{"n": i, "tier": "REVIEW", "asunto": "a",
                         "remitente": "r", "score": 1,
                         "modo_scoring": "determinista"} for i in (1, 2)]
            out = th.cmd_informe({"session_id": "s1", "modo": "simulacion",
                                  "unidades": unidades})
            self.assertTrue(out["ok"], out)
            self.assertEqual(out["lectura_recortada"], 1)
            md = open(out["ruta"], encoding="utf-8").read()
            self.assertIn("Lectura recortada en 1 correos", md)
            self.assertIn("#m2", md)
            # Sin recortes, ni aviso ni campo.
            th.cmd_registrar(ruta, {"ts": "t", "desglose":
                                    th.cmd_scoring_dispatch(
                                        {"emails": [correo(2, TEXTO)]}, CFG)})
            out = th.cmd_informe({"session_id": "s1", "modo": "simulacion",
                                  "unidades": unidades})
            self.assertNotIn("lectura_recortada", out)


if __name__ == "__main__":
    unittest.main()
