"""`scripts/correos_lector.py`: el banco de boletines largos (BANCO=lector).

Fija lo que lo hace distinto del banco de 120: cuerpos que `sanitizar`
recorta (el extracto acaba en «[truncado]»), remitentes inventados y unos
esperados con las mismas letras de controles. Sin red.
"""
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(_RAIZ, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(_RAIZ, "scripts"))

from tests import DIR_SCRIPTS  # noqa: E402,F401  (pone la skill en sys.path)
import correos_lector as cl  # noqa: E402
import triage_helpers as th  # noqa: E402

TIERS = {"REPLY_NEEDED", "REVIEW", "READING_LATER", "ARCHIVE"}


class TestBancoLector(unittest.TestCase):
    def test_esperados_alineados_y_validos(self):
        self.assertEqual(len(cl.CORREOS), len(cl.ESPERADOS))
        for tier, letras in cl.ESPERADOS:
            self.assertIn(tier, TIERS)
            self.assertLessEqual(set(letras), set("PDBF"))

    def test_remitentes_inventados(self):
        for _, remitente, _ in cl.CORREOS:
            self.assertTrue(remitente.endswith("example.invalid"), remitente)

    def test_todos_se_recortan(self):
        """Más de 1.500 caracteres: el extracto que reciben el principal y el
        evaluador acaba en «[truncado]», como un boletín real."""
        for asunto, remitente, cuerpo in cl.CORREOS:
            s = th.cmd_sanitizar(cuerpo, 1500, asunto, remitente)
            self.assertFalse(s["injection"], asunto)
            self.assertTrue(th.ancla_extracto(s["texto"])["fin"].endswith("[truncado]"),
                            asunto)

    def test_el_recorte_por_si_solo_no_rompe_el_eco(self):
        """Un eco que copia las últimas palabras del extracto sin la marca
        «[truncado]» sigue valiendo: el recorte no explica por sí solo los
        fallos de eco con correo real (11 de 55, Gemini, 2026-11-03)."""
        for asunto, remitente, cuerpo in cl.CORREOS:
            texto = th.cmd_sanitizar(cuerpo, 1500, asunto, remitente)["texto"]
            ancla = th.ancla_extracto(texto)
            palabras = texto.replace("[truncado]", "").split()
            eco = {"inicio": " ".join(palabras[:8]), "fin": " ".join(palabras[-8:])}
            self.assertTrue(th.eco_coincide(eco, ancla), asunto)


if __name__ == "__main__":
    unittest.main()
