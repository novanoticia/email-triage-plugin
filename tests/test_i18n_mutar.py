"""La herramienta de sabotaje: sus mutantes se aplican y un superviviente da exit 1."""
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import i18n_mutar as mu  # noqa: E402


class TestAplicabilidad(unittest.TestCase):
    def test_cada_mutante_se_puede_aplicar_exactamente_una_vez_al_repositorio_real(self):
        for m in mu.MUTANTES:
            with self.subTest(mutante=m[0]):
                self.assertEqual(mu.apariciones(m, RAIZ), 1,
                                 "el texto a mutar debe aparecer exactamente 1 vez")

    def test_hay_mutantes_de_todas_las_capas(self):
        ficheros = " ".join(m[1] for m in mu.MUTANTES)
        for capa in ("idioma.py", "en.yaml", "fr.yaml", "SKILL.md", "README.md",
                     "i18n_validar.py", "i18n_extraer.py", "i18n_baseline.py", "tests.yml"):
            self.assertIn(capa, ficheros)

    def test_los_mutantes_no_cambian_nada_por_si_solos(self):
        for m in mu.MUTANTES:
            self.assertNotEqual(m[2], m[3], m[0])


class TestRegistro(unittest.TestCase):
    """tests/escenarios.md registra los mutantes: las cifras citadas no pueden desfasarse."""

    def setUp(self):
        with open(os.path.join(RAIZ, "tests", "escenarios.md"), encoding="utf-8") as f:
            self.doc = f.read()

    def test_cada_mutante_esta_registrado(self):
        for m in mu.MUTANTES:
            self.assertIn(m[0], self.doc)

    def test_el_recuento_citado_coincide_con_los_mutantes(self):
        self.assertIn(f"{len(mu.MUTANTES)} mutantes", self.doc)

    def test_declara_que_los_tests_de_frases_son_de_instantanea(self):
        self.assertIn("instantánea", self.doc)

    def test_declara_los_limites_de_la_simulacion_o_su_ausencia_de_plataforma_real(self):
        self.assertIn("no es una plataforma real", self.doc.lower().replace("**", ""))


class TestMecanismo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = self.tmp.name
        with open(os.path.join(self.raiz, "f.txt"), "w", encoding="utf-8") as f:
            f.write("hola mundo\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_mutante_muerto_si_el_runner_falla(self):
        m = ("x", "f.txt", "hola", "adiós")
        vistos = []

        def correr(copia):
            with open(os.path.join(copia, "f.txt"), encoding="utf-8") as f:
                vistos.append(f.read())
            return 1  # las pruebas fallan => el mutante muere
        self.assertEqual(mu.ejecutar([m], self.raiz, correr), [])
        self.assertEqual(vistos, ["adiós mundo\n"])
        with open(os.path.join(self.raiz, "f.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "hola mundo\n", "el original no se toca")

    def test_mutante_superviviente_si_el_runner_pasa(self):
        m = ("x", "f.txt", "hola", "adiós")
        self.assertEqual(mu.ejecutar([m], self.raiz, lambda copia: 0), ["x"])

    def test_mutante_no_aplicable_cuenta_como_superviviente(self):
        m = ("y", "f.txt", "no existe", "z")
        self.assertEqual(mu.ejecutar([m], self.raiz, lambda copia: 1), ["y (no aplicable)"])

    def test_exit_code_del_main(self):
        self.assertEqual(mu.codigo_de_salida([]), 0)
        self.assertEqual(mu.codigo_de_salida(["x"]), 1)


if __name__ == "__main__":
    unittest.main()
