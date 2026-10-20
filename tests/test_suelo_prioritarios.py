"""suelo_prioritarios (v3.21.22): un prioritario no baja del tier elegido.

Prueba real 2026-10-20: 12 correos de remitentes prioritarios (Žižek,
Sociología Inquieta) cayeron en ARCHIVE porque el +3 no compensa
sender_bulk, coste cognitivo y manipulación. `filtros.suelo_prioritarios`
(opt-in) fija el tier mínimo; sin él, nada cambia. Sin red.
"""
import copy
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

if DIR_SCRIPTS not in sys.path:
    sys.path.insert(0, DIR_SCRIPTS)
import triage_helpers as th  # noqa: E402

CFG = {
    "criterios_epistemicos": {
        "a": {"activo": True, "core": True, "eje": "valor_decisional",
              "si": 5, "no": -5}},
    "scoring": {"ejes": {"valor_decisional": [-10, 10]}},
    "tiers": {"reply_needed": 10, "review": 4, "reading_later": 0,
              "archive": -1},
    "hard_rules": {"sender_bulk_penalizacion": -4},
    "filtros": {"remitentes_prioritarios": ["slavoj@substack.com"]},
}
# El caso real: newsletter de un prioritario, -5 + -4 de bulk + 3 = -6.
ZIZEK = {"verdicts": {"a": "no"}, "hard_rules": ["sender_bulk_penalizacion"],
         "extra_points": 3, "prioritario": True}


def _cfg(suelo):
    c = copy.deepcopy(CFG)
    c["filtros"]["suelo_prioritarios"] = suelo
    return c


class TestSueloPrioritarios(unittest.TestCase):
    def test_sin_suelo_nada_cambia(self):
        for cfg in (CFG, _cfg(None)):
            r = th.cmd_scoring(dict(ZIZEK), cfg)
            self.assertEqual(r["tier"], "ARCHIVE")
            self.assertNotIn("suelo_aplicado", r)

    def test_reading_later_saca_al_prioritario_de_archive(self):
        r = th.cmd_scoring(dict(ZIZEK), _cfg("READING_LATER"))
        self.assertEqual(r["tier"], "READING_LATER")
        self.assertEqual(r["suelo_aplicado"],
                         "ARCHIVE->READING_LATER (remitente prioritario)")
        self.assertEqual(r["score"], -6)          # el score no se toca

    def test_review_como_suelo(self):
        r = th.cmd_scoring(dict(ZIZEK), _cfg("REVIEW"))
        self.assertEqual(r["tier"], "REVIEW")

    def test_no_baja_un_tier_que_ya_esta_por_encima(self):
        alto = dict(ZIZEK, verdicts={"a": "si"}, hard_rules=[])   # 5+3=8
        r = th.cmd_scoring(alto, _cfg("READING_LATER"))
        self.assertEqual(r["tier"], "REVIEW")
        self.assertNotIn("suelo_aplicado", r)

    def test_solo_con_prioritario_true_literal(self):
        for valor in (None, False, "true", 1, "si"):
            with self.subTest(valor=valor):
                p = dict(ZIZEK, prioritario=valor)
                r = th.cmd_scoring(p, _cfg("READING_LATER"))
                self.assertEqual(r["tier"], "ARCHIVE")

    def test_el_cap_por_inyeccion_manda(self):
        p = dict(ZIZEK, tier_maximo="READING_LATER")
        r = th.cmd_scoring(p, _cfg("REVIEW"))
        self.assertEqual(r["tier"], "READING_LATER")

    def test_reply_needed_no_es_un_suelo(self):
        for suelo in ("REPLY_NEEDED", "archive", 2, True, ["REVIEW"]):
            with self.subTest(suelo=suelo):
                r = th.cmd_scoring(dict(ZIZEK), _cfg(suelo))
                self.assertEqual(r["tier"], "ARCHIVE")

    def test_brief_muestra_el_suelo(self):
        out = th.cmd_scoring_dispatch({"emails": [dict(ZIZEK, id=1)]},
                                      _cfg("READING_LATER"), brief=True)
        self.assertIn("suelo_aplicado", out["resultados"][0])

    def test_coincidencias_dice_prioritario_y_suelo(self):
        r = th.cmd_coincidencias(
            {"correos": [{"id": 1, "remitente":
                          "Slavoj <slavoj+politics@substack.com>",
                          "asunto": "AI 1"}]}, _cfg("READING_LATER"))
        self.assertTrue(r["resultados"][0]["prioritario"])
        self.assertEqual(r["suelo_prioritarios"], "READING_LATER")

    def test_validar_config_avisa_de_un_suelo_invalido(self):
        avisos, info = th._avisos_config_usuario(_cfg("REPLY_NEEDED"))
        self.assertTrue(any("suelo_prioritarios" in a for a in avisos))
        self.assertIsNone(info["suelo_prioritarios_efectivo"])
        avisos, info = th._avisos_config_usuario(_cfg("READING_LATER"))
        self.assertFalse(any("suelo_prioritarios" in a for a in avisos))
        self.assertEqual(info["suelo_prioritarios_efectivo"], "READING_LATER")


if __name__ == "__main__":
    unittest.main()
