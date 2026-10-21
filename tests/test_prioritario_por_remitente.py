"""prioritario por remitente (v3.21.27): el script decide, no el modelo.

Prueba real 2026-10-21 (Opus, dry-run): tres correos de Žižek, remitente
prioritario, salieron en ARCHIVE porque el modelo no pasó `prioritario` al
scoring; luego aplicó el suelo «a mano». Si el payload trae `remitente`, el
script comprueba él mismo la lista con las reglas de `coincidencias`. Sin red.
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
    "filtros": {"remitentes_prioritarios": ["slavoj@substack.com"],
                "suelo_prioritarios": "READING_LATER"},
}
BASE = {"verdicts": {"a": "no"}, "hard_rules": ["sender_bulk_penalizacion"],
        "extra_points": 3}
ZIZEK = "Slavoj Žižek <slavoj+news@substack.com>"


def _p(**extra):
    p = copy.deepcopy(BASE)
    p.update(extra)
    return p


class TestPrioritarioPorRemitente(unittest.TestCase):
    def test_el_caso_real_sin_flag_pero_con_remitente(self):
        r = th.cmd_scoring(_p(remitente=ZIZEK), CFG)
        self.assertEqual(r["tier"], "READING_LATER")
        self.assertIn("suelo_aplicado", r)
        self.assertTrue(r["prioritario_verificado"])
        self.assertNotIn("aviso_prioritario", r)

    def test_el_remitente_manda_sobre_el_flag(self):
        r = th.cmd_scoring(_p(remitente=ZIZEK, prioritario=False), CFG)
        self.assertEqual(r["tier"], "READING_LATER")
        self.assertIn("aviso_prioritario", r)
        r = th.cmd_scoring(_p(remitente="otro@x.com", prioritario=True), CFG)
        self.assertEqual(r["tier"], "ARCHIVE")
        self.assertIn("aviso_prioritario", r)

    def test_el_nombre_visible_no_basta(self):
        # Igual que coincidencias: «Slavoj <atacante@y>» no es prioritario.
        r = th.cmd_scoring(_p(remitente="slavoj@substack.com <a@y.com>"), CFG)
        self.assertEqual(r["tier"], "ARCHIVE")

    def test_sin_remitente_se_comporta_como_antes_y_lo_dice(self):
        r = th.cmd_scoring(_p(prioritario=True), CFG)
        self.assertEqual(r["tier"], "READING_LATER")
        self.assertFalse(r["prioritario_verificado"])
        r = th.cmd_scoring(_p(), CFG)
        self.assertEqual(r["tier"], "ARCHIVE")
        self.assertFalse(r["prioritario_verificado"])

    def test_sin_suelo_no_hay_campos_nuevos(self):
        cfg = copy.deepcopy(CFG)
        del cfg["filtros"]["suelo_prioritarios"]
        r = th.cmd_scoring(_p(remitente=ZIZEK), cfg)
        self.assertEqual(r["tier"], "ARCHIVE")
        self.assertNotIn("prioritario_verificado", r)

    def test_remitente_no_texto_se_ignora(self):
        for malo in (None, 3, ["slavoj@substack.com"], {"a": 1}):
            r = th.cmd_scoring_dispatch(_p(remitente=malo), CFG)
            self.assertIn("tier", r, malo)
            self.assertFalse(r["prioritario_verificado"], malo)

    def test_el_lote_cuenta_los_no_verificados(self):
        lote = {"emails": [_p(id=1, remitente=ZIZEK), _p(id=2),
                           _p(id=3, prioritario=True)]}
        r = th.cmd_scoring_dispatch(lote, CFG)
        self.assertEqual(r["prioritario_sin_verificar"], 2)
        r = th.cmd_scoring_dispatch(lote, CFG, brief=True)
        self.assertEqual(r["prioritario_sin_verificar"], 2)
        self.assertTrue(r["resultados"][0]["prioritario_verificado"])

    def test_el_lote_sin_suelo_no_cuenta(self):
        cfg = copy.deepcopy(CFG)
        del cfg["filtros"]["suelo_prioritarios"]
        r = th.cmd_scoring_dispatch({"emails": [_p(id=1)]}, cfg)
        self.assertNotIn("prioritario_sin_verificar", r)


if __name__ == "__main__":
    unittest.main()
