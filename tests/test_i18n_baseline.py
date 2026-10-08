"""El idioma por defecto no cambia: línea base por hashes de línea."""
import hashlib
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import i18n_baseline as lb  # noqa: E402

# Huella del bloque S0 francés (v3.14.1), única excepción funcional a la línea base.
# Congelarlo impide que cualquier otra línea colada en ese rango quede exenta.
# Si cambias los patrones franceses a propósito: verifica TestS0Frances y recalcula.
HUELLA_S0_FR = "93a5549fcaba6ec6e4b13e8ba49dc4fe44381dc5"


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


class TestNormalizacionDeVersion(unittest.TestCase):
    """El bump de versión es la única excepción: lo normalizado no puede ocultar otros cambios."""

    def h(self, linea):
        return lb.hash_linea(linea)

    def test_misma_linea_con_distinta_version_da_el_mismo_hash(self):
        pares = [('  version: "3.13.5"', '  version: "3.14.0"'),
                 ('  version: "3.14.0"', '  version: "3.14.1"'),
                 ("# Email Triage v3.13 — Filtrado", "# Email Triage v3.14 — Filtrado"),
                 ("# EMAIL TRIAGE v3.13", "# EMAIL TRIAGE v3.14"),
                 ("plugin email-triage (v3.13.5)", "plugin email-triage (v3.14.0)"),
                 ("plugin email-triage (v3.14.0)", "plugin email-triage (v3.14.1)"),
                 # Parches futuros: no exigen tocar el regex en cada bump.
                 ('  version: "3.14.1"', '  version: "3.14.2"'),
                 ("plugin email-triage (v3.14.1)", "plugin email-triage (v3.14.10)")]
        for a, b in pares:
            with self.subTest(a=a):
                self.assertEqual(self.h(a), self.h(b))

    def test_otros_numeros_no_se_normalizan(self):
        for a, b in [("RESUMEN DE TRIAJE v3.0", "RESUMEN DE TRIAJE v3.1"),
                     ("hasta 3.9 usuarios", "hasta 3.8 usuarios"),
                     ("versión 13.13.5", "versión 13.14.5"),
                     ("# Email Triage v3.13 — A", "# Email Triage v3.13 — B")]:
            with self.subTest(a=a):
                self.assertNotEqual(self.h(a), self.h(b))


class TestLineaBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(lb.RUTA_BASE, encoding="utf-8") as f:
            cls.base = json.load(f)

    def test_la_base_coincide_con_el_commit_base_si_esta_disponible(self):
        import subprocess
        try:
            subprocess.run(["git", "cat-file", "-e", self.base["commit_base"] + "^{commit}"],
                           cwd=RAIZ, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("el commit base %s no está en este clon (¿clon superficial del CI?): "
                          "la línea base solo se contrasta con git cuando existe" % self.base["commit_base"])
        recien = lb.calcular(commit=self.base["commit_base"])
        self.assertEqual(recien["ficheros"], self.base["ficheros"])

    def test_hay_ficheros_en_la_base(self):
        self.assertGreaterEqual(len(self.base["ficheros"]), 15)

    def test_cada_fichero_original_conserva_sus_lineas(self):
        for rel, esperado in self.base["ficheros"].items():
            with self.subTest(fichero=rel):
                actual = lb.hashes_de(os.path.join(RAIZ, rel))
                if rel.endswith("/scripts/triage_helpers.py"):
                    # v3.14.1 amplía S0 con francés: cambio funcional deliberado,
                    # fijado por TestS0Frances, no una traducción de la interfaz.
                    # Solo se excluye el bloque añadido; el original se conserva.
                    inicio = lb.hash_linea("# Francés: mismas categorías y mismas vistas S0, con independencia del idioma")
                    fin = lb.hash_linea("S1_CORTES = [")
                    if inicio in actual:
                        i = actual.index(inicio)
                        j = actual.index(fin, i)
                        huella = hashlib.sha1("".join(actual[i:j]).encode()).hexdigest()
                        self.assertEqual(huella, HUELLA_S0_FR,
                                         "el bloque S0 francés cambió: revisa TestS0Frances "
                                         "y recalcula HUELLA_S0_FR a conciencia")
                        actual = actual[:i] + actual[j:]
                if actual != esperado:
                    n = next((i for i, (a, b) in enumerate(zip(actual, esperado)) if a != b),
                             min(len(actual), len(esperado)))
                    self.fail(f"{rel}: difiere desde la línea {n + 1} "
                              f"(actual {len(actual)} líneas, base {len(esperado)})")


if __name__ == "__main__":
    unittest.main()
