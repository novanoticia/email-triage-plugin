"""El idioma por defecto no cambia: línea base por hashes de línea."""
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import i18n_baseline as lb  # noqa: E402


class TestQuitarBloques(unittest.TestCase):
    def test_quita_bloque_y_una_linea_en_blanco(self):
        ent = ["a", "", lb.INI, "x", lb.FIN, "", "b"]
        self.assertEqual(lb.quitar_bloques(ent), ["a", "", "b"])

    def test_bloque_sin_cerrar_falla(self):
        with self.assertRaises(ValueError):
            lb.quitar_bloques(["a", lb.INI, "x"])

    def test_fin_sin_inicio_falla(self):
        with self.assertRaises(ValueError):
            lb.quitar_bloques(["a", lb.FIN])

    def test_texto_sin_bloques_no_cambia(self):
        self.assertEqual(lb.quitar_bloques(["a", "b"]), ["a", "b"])


class TestLineaBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(lb.RUTA_BASE, encoding="utf-8") as f:
            cls.base = json.load(f)

    def test_hay_ficheros_en_la_base(self):
        self.assertGreaterEqual(len(self.base["ficheros"]), 15)

    def test_cada_fichero_original_conserva_sus_lineas(self):
        for rel, esperado in self.base["ficheros"].items():
            with self.subTest(fichero=rel):
                actual = lb.hashes_de(os.path.join(RAIZ, rel))
                if actual != esperado:
                    n = next((i for i, (a, b) in enumerate(zip(actual, esperado)) if a != b),
                             min(len(actual), len(esperado)))
                    self.fail(f"{rel}: difiere desde la línea {n + 1} "
                              f"(actual {len(actual)} líneas, base {len(esperado)})")


if __name__ == "__main__":
    unittest.main()
