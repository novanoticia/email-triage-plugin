"""El informe se escribe antes del resumen (v3.21.32).

Pruebas reales 2026-10-21 (tres dry-runs seguidos): nunca apareció la
línea `📄 Informe:`. Dos causas en el texto: el PASO 5 (resumen) iba antes
que el 5.R (informe), y el formato de simulación de salidas-por-modo.md no
tenía esa línea, así que el modelo cerraba la sesión sin llegar al 5.R.
"""
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

SKILL_DIR = os.path.dirname(DIR_SCRIPTS)
LINEA = "📄 Informe: [ruta del informe]"


def _leer(*partes):
    with open(os.path.join(SKILL_DIR, *partes), encoding="utf-8") as fh:
        return fh.read()


class TestInformeEnResumen(unittest.TestCase):
    def test_paso5_manda_escribir_antes_el_informe(self):
        s = _leer("SKILL.md")
        i = s.index("## PASO 5 — RESUMEN DE SESIÓN")
        cabeza = s[i:s.index("### Resumen de sesión real", i)]
        self.assertIn("Escribe antes el informe (PASO 5.R)", cabeza)
        self.assertIn("también en simulación", cabeza)

    def test_los_tres_formatos_de_resumen_citan_el_informe(self):
        self.assertIn(LINEA, _leer("SKILL.md"))
        m = _leer("references", "salidas-por-modo.md")
        sim = m[m.index("modo simulación"):m.index("modo rutina")]
        rutina = m[m.index("modo rutina"):]
        self.assertIn(LINEA, sim)
        self.assertIn(LINEA, rutina)


if __name__ == "__main__":
    unittest.main()
