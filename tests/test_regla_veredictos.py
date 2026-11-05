"""Veredictos de esta sesión (v3.28.2, decisión del mantenedor).

Prueba real 2026-11-03: para comparar con Gemini, la sesión reutilizó los
veredictos de una simulación anterior «sin releer los textos» y generó otros
con un script propio por categoría (30 de 89 correos con
`plantilla_cercana`). En una simulación que compara proveedores reutilizar
tiene una ventaja (todos se miden contra la misma referencia), pero el
principal deja de ser una medición independiente; en real, un correo no
leído contaría como triaje.

La regla vive en el SKILL.md, en el bloque de delegación justo antes de la
evaluación: prohibido en real y en rutina; en simulación, solo declarado en
el informe. Es doctrina: `plantilla` y `plantilla_cercana` siguen siendo el
freno mecánico de los veredictos asignados en serie. Sin red.
"""
import os
import re
import unittest

from tests import DIR_SCRIPTS

RUTA_SKILL = os.path.join(os.path.normpath(os.path.join(DIR_SCRIPTS, "..")),
                          "SKILL.md")


def _regla():
    with open(RUTA_SKILL, encoding="utf-8") as f:
        texto = f.read()
    m = re.search(r"\*\*Veredictos de esta sesión \(v[\d.]+\).*?(?=\n<!-- i18n:fin -->)",
                  texto, re.S)
    return (texto, " ".join(m.group(0).split()) if m else "")


class TestReglaVeredictos(unittest.TestCase):
    def test_la_regla_va_antes_de_la_evaluacion(self):
        texto, regla = _regla()
        self.assertTrue(regla, "falta la regla de veredictos en el SKILL.md")
        pos = texto.index("**Veredictos de esta sesión (")
        self.assertLess(texto.rfind("Sin delegación, sigue este paso.", 0, pos), pos)
        self.assertLess(pos, texto.index("El modelo evalúa cada correo contra"))

    def test_dice_lo_que_decidio_el_mantenedor(self):
        _, regla = _regla()
        for trozo in ("leer en esta sesión el texto saneado de ese correo",
                      "nunca de otra sesión, de otro correo",
                      "script tuyo", "En real y en rutina, sin excepción",
                      "Solo en simulación", "si lo dices en el informe",
                      "con cuántos son", "nunca como evaluación nueva"):
            self.assertIn(trozo, regla)


if __name__ == "__main__":
    unittest.main()
