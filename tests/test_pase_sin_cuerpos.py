"""Pase sin cuerpos (v3.21.28): con ≤200 correos nunca se clasifica por
remitente/asunto solamente.

Pruebas reales 2026-10-20 y 2026-10-21 (60 y 96 correos): el modelo
estiró la sugerencia de 4.H («>200 correos: sugerir un primer pase
rápido») y presentó tiers sin haber leído ningún cuerpo. Es instrucción,
no mecanismo; el test fija que la regla no se pierda en una edición.
"""
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

SKILL = os.path.join(os.path.dirname(DIR_SCRIPTS), "SKILL.md")


class TestPaseSinCuerpos(unittest.TestCase):
    def setUp(self):
        with open(SKILL, encoding="utf-8") as fh:
            self.texto = fh.read()
        i = self.texto.index("### 4.H")
        self.h = self.texto[i:self.texto.index("### 4.I", i)]

    def test_el_pase_rapido_exige_mas_de_200_y_permiso(self):
        self.assertIn(">200 correos y si la persona acepta", self.h)
        self.assertIn("Con ≤200, nunca.", self.h)

    def test_sin_cuerpos_no_hay_tiers(self):
        self.assertIn("Sin cuerpos no hay triaje: no des tiers.", self.h)

    def test_ya_no_se_sugiere_por_iniciativa_propia(self):
        self.assertNotIn("sugerir un primer pase rápido", self.texto)


if __name__ == "__main__":
    unittest.main()
