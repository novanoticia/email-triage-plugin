"""Reglas del pipeline que el modelo debe respetar (problemas vistos en las
pruebas reales del mantenedor, 2026-10-17/18).

Son instrucciones del SKILL, no mecanismos: este test fija que el texto
existe y es coherente para que no desaparezca en silencio. Solo stdlib.
"""
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

SKILL_DIR = os.path.dirname(DIR_SCRIPTS)


def _leer(*partes):
    with open(os.path.join(SKILL_DIR, *partes), encoding="utf-8") as f:
        return f.read()


class TestVeredictosNoSeAjustanAlReparto(unittest.TestCase):
    """Prueba 3: el modelo «recalibró» veredictos porque 134 de 148 caían
    en REVIEW. El reparto se informa; no se corrige retocando juicios."""

    @classmethod
    def setUpClass(cls):
        cls.skill = _leer("SKILL.md")

    def test_regla_en_errores_comunes(self):
        errores = self.skill.split("## Errores comunes a evitar", 1)[1]
        self.assertIn("No ajustes veredictos para obtener un reparto", errores)
        self.assertIn("dilo en el resumen como hallazgo", errores)

    def test_regla_junto_a_la_invocacion_del_scoring(self):
        i = self.skill.index("**Cómo se invoca** (solo en modo determinista)")
        self.assertIn("Fija los veredictos de cada correo",
                      self.skill[i:i + 400])


class TestSimulacionYDesglose(unittest.TestCase):
    """v3.21.0 permitió `guardar_desglose` en simulación: las dos reglas de
    simulación deben nombrar esa excepción para no contradecirla."""

    def test_skill_y_referencia_nombran_la_excepcion(self):
        skill = _leer("SKILL.md")
        linea = next(l for l in skill.splitlines()
                     if l.startswith("- En modo simulación, NUNCA"))
        self.assertIn("guardar_desglose", linea)
        self.assertIn("guardar_desglose", _leer("references", "modo-simulacion.md"))


if __name__ == "__main__":
    unittest.main()
