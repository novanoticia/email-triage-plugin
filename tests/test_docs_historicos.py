"""Los planes ejecutados no deben leerse como instrucciones vigentes (auditoría 2026-10-08, F5)."""
import os
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CABECERA = "<!-- DOCUMENTO HISTÓRICO — NO CONTIENE INSTRUCCIONES VIGENTES -->"
# Planes ya ejecutados. Un plan en curso NO lleva la cabecera; al cerrarlo, añádelo aquí.
EJECUTADOS = ["2026-10-07-multiidioma.md"]


class TestPlanesHistoricos(unittest.TestCase):
    def test_cada_plan_ejecutado_empieza_con_la_cabecera_historica(self):
        for nombre in EJECUTADOS:
            p = os.path.join(RAIZ, "docs", "superpowers", "plans", nombre)
            with self.subTest(plan=os.path.relpath(p, RAIZ)):
                with open(p, encoding="utf-8") as f:
                    self.assertEqual(f.readline().rstrip("\n"), CABECERA)


if __name__ == "__main__":
    unittest.main()
