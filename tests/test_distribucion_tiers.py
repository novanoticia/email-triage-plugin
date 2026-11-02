"""Tests de scripts/distribucion_tiers.py (herramienta de desarrollo, solo lee)."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
sys.path.insert(0, os.path.join(RAIZ, "plugins/email-triage/skills/email-triage/scripts"))
import distribucion_tiers as dt  # noqa: E402


def fila(i, score, tier, **extra):
    r = {"id": str(i), "score": score, "tier": tier,
         "ejes": {"valor_decisional": 0, "calidad_epistemica": score,
                  "riesgo_manipulacion": 0, "coste_cognitivo": 0, "presion_accion": 0},
         "hard_puntos": 0, "extra_points": 0}
    r.update(extra)
    return r


class TestDistribucion(unittest.TestCase):
    def test_tramos_y_umbrales(self):
        rs = [fila(1, -1, "ARCHIVE"), fila(2, -2, "ARCHIVE", hard_puntos=-4),
              fila(3, -4, "ARCHIVE"), fila(4, -18, "ARCHIVE"),
              fila(5, 2, "READING_LATER"), fila(6, 20, "REVIEW"), {"id": "7"}]
        d = dt.distribucion(rs, 0)
        self.assertEqual(d["correos"], 6)
        self.assertEqual(d["ignorados"], 1)
        self.assertEqual(d["tiers"]["ARCHIVE"], 4)
        tramos = {t["tramo"]: t for t in d["tramos_archive"]}
        self.assertEqual(tramos[(-2, None)]["correos"], 2)
        self.assertEqual(tramos[(-2, None)]["con_otras_penalizaciones"], 1)
        self.assertEqual(tramos[(-5, -2)]["correos"], 1)
        self.assertEqual(tramos[(None, -10)]["correos"], 1)
        self.assertEqual(d["pasarian_a_reading_later"], {-1: 1, -2: 2, -3: 2, -5: 3})

    def test_scores_decimales_caen_en_algun_tramo(self):
        # Revisión de Codex (PR #180): el motor admite decimales; con tramos
        # de enteros, -0.5 o -2.5 no caían en ninguno.
        rs = [fila(i, s, "ARCHIVE") for i, s in enumerate((-0.5, -2.5, -5.5, -10.5, -10))]
        d = dt.distribucion(rs, 0)
        self.assertEqual(sum(t["correos"] for t in d["tramos_archive"]), len(rs))
        tramos = {t["tramo"]: t["correos"] for t in d["tramos_archive"]}
        self.assertEqual(tramos, {(-2, None): 1, (-5, -2): 1, (-10, -5): 2, (None, -10): 1})

    def test_riesgo_negativo_cuenta_como_otra_penalizacion(self):
        r = fila(1, -1, "ARCHIVE")
        r["ejes"]["riesgo_manipulacion"] = -3
        self.assertTrue(dt._otras_penalizaciones(r))
        self.assertFalse(dt._otras_penalizaciones(fila(2, -1, "ARCHIVE")))

    def test_lee_desglose_acumulado_con_ultima_pasada_y_no_imprime_texto(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "sesion.jsonl")
            secreto = "Asunto ficticio que no debe salir"
            primera = {"resultados": [fila(1, 5, "REVIEW", asunto=secreto)]}
            ultima = {"resultados": [fila(1, -2, "ARCHIVE", asunto=secreto)]}
            with open(ruta, "w", encoding="utf-8") as fh:
                for p in (primera, ultima):
                    fh.write(json.dumps({"ts": "x", "desglose": p}) + "\n")
            salida = io.StringIO()
            with redirect_stdout(salida):
                self.assertEqual(dt.main([ruta]), 0)
            texto = salida.getvalue()
            self.assertIn("correos: 1", texto)
            self.assertNotIn(secreto, texto)
            self.assertNotIn("REVIEW          1", texto)  # cuenta solo la última pasada


    def test_desglose_demasiado_grande_se_omite_entero(self):
        # Revisión de Codex (PR #180): leer solo el principio perdería las
        # últimas pasadas y contaría tiers antiguos sin avisar.
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "grande.jsonl")
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": "x", "desglose": {"resultados": [fila(1, -1, "ARCHIVE")]}}) + "\n")
            original = dt.th.MAX_INGESTA_BYTES
            dt.th.MAX_INGESTA_BYTES = 20
            try:
                resultados, ilegibles, grandes = dt._leer([ruta])
            finally:
                dt.th.MAX_INGESTA_BYTES = original
            self.assertEqual((resultados, ilegibles, grandes), ([], 0, 1))


if __name__ == "__main__":
    unittest.main()
