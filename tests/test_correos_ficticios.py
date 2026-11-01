"""Coherencia de los tiers esperados de los correos inventados (scripts/)."""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
sys.path.insert(0, os.path.join(RAIZ, "plugins/email-triage/skills/email-triage/scripts"))
import clasificadores as nc  # noqa: E402
import correos_ficticios as cf  # noqa: E402

TIERS = {"REPLY_NEEDED", "REVIEW", "READING_LATER", "ARCHIVE"}


class TestCorreosFicticios(unittest.TestCase):
    def test_un_esperado_por_correo(self):
        self.assertEqual(len(cf.ESPERADOS), len(cf.CORREOS))

    def test_tiers_y_letras_validos(self):
        for tier, letras in cf.ESPERADOS:
            self.assertIn(tier, TIERS)
            self.assertLessEqual(set(letras), set("PDBF"))
            # F fija REPLY_NEEDED; sin F el scoring lo capa a REVIEW.
            self.assertEqual("F" in letras, tier == "REPLY_NEEDED")

    def test_controles_aceptados_por_el_nucleo(self):
        for _, letras in cf.ESPERADOS:
            nc._validar_control(cf.control(letras))
        self.assertEqual(cf.control(""), {
            "hard_rules": [], "extra_points": 0, "forzar_reply_needed": False,
            "tier_maximo": None, "remitente_en_historial": False})

    def test_reglas_definidas_en_config(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML no instalado")
        cfg = yaml.safe_load(open(os.path.join(
            RAIZ, "plugins/email-triage/skills/email-triage/config.yaml"), encoding="utf-8"))
        self.assertLessEqual(set(cf.REGLAS.values()), set(cfg["hard_rules"]))


if __name__ == "__main__":
    unittest.main()
