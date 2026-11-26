"""Tabla de boosts del 4.A.2 frente al PASO 2 (v3.28.16, decisión del mantenedor).

Prueba real 2026-11-25: `paso-2-calibracion.md` daba +1 a los correos cuyo
asunto contiene una de las `top_keywords` (top 15) de la calibración, pero la
tabla del 4.A.2 del `SKILL.md` no lo recogía, y el modelo no lo aplicó («el
SKILL no lo recoge en 4.A.2»). El mantenedor decidió añadirlo a la tabla.
Este test vigila que los dos documentos digan lo mismo. Sin red.
"""
import os
import re
import unittest

from tests import DIR_SCRIPTS

SKILL_DIR = os.path.normpath(os.path.join(DIR_SCRIPTS, ".."))


def _leer(*partes):
    with open(os.path.join(SKILL_DIR, *partes), encoding="utf-8") as f:
        return f.read()


class TestTablaBoosts(unittest.TestCase):
    def test_tabla_recoge_el_boost_de_keywords_del_historial(self):
        texto = _leer("SKILL.md")
        inicio = texto.index("#### 4.A.2")
        tabla = texto[inicio:texto.index("#### 4.A.3", inicio)]
        fila = re.search(r"^\| \*\*Keyword del historial\*\* \| \+1 \| (.+) \|$", tabla, re.M)
        self.assertTrue(fila, "falta la fila de keywords del historial en el 4.A.2")
        self.assertIn("`top_keywords` (top 15)", fila.group(1))
        self.assertIn("+1 por correo", fila.group(1))

    def test_paso_2_dice_lo_mismo(self):
        paso2 = " ".join(_leer("references", "paso-2-calibracion.md").split())
        self.assertIn("Dar +1 punto a correos cuyo asunto contiene keywords del top 15", paso2)


if __name__ == "__main__":
    unittest.main()
