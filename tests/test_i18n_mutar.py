"""La herramienta de sabotaje: sus mutantes se aplican y un superviviente da exit 1."""
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import i18n_mutar as mu  # noqa: E402


@unittest.skipIf(os.environ.get("I18N_MUTANDO"),
                 "dentro de la copia mutada este test fallaría siempre (ver TestLaCopiaMutadaNoSeAutoMata)")
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

    def test_registra_la_correccion_de_la_auto_muerte_de_los_mutantes(self):
        self.assertIn("auto-muerte", " ".join(self.doc.split()))
        self.assertIn("26 de 27", " ".join(self.doc.split()))

    def test_declara_que_los_tests_de_frases_son_de_instantanea(self):
        self.assertIn("instantánea", self.doc)

    def test_declara_los_limites_de_la_simulacion_o_su_ausencia_de_plataforma_real(self):
        self.assertIn("no es una plataforma real", self.doc.lower().replace("**", ""))


class TestLaCopiaMutadaNoSeAutoMata(unittest.TestCase):
    """Dentro de la copia mutada, el test de aplicabilidad falla siempre (el texto ya no
    está): sin evitarlo, TODO mutante «moriría» por ese test y el sabotaje no mediría nada."""

    def test_el_entorno_de_mutacion_se_marca(self):
        self.assertEqual(mu.entorno_de_mutacion().get("I18N_MUTANDO"), "1")

    def test_la_aplicabilidad_se_omite_en_la_copia_mutada_y_falla_fuera_de_ella(self):
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            copia = os.path.join(tmp, "r")
            shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns(
                ".git", "__pycache__", ".superpowers"))
            ruta = os.path.join(copia, "plugins", "email-triage", "skills", "email-triage",
                                "scripts", "idioma.py")
            with open(ruta, encoding="utf-8") as f:
                t = f.read()
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(t.replace("marcas[0]", "marcas[-1]"))
            cmd = [sys.executable, "-m", "unittest", "tests.test_i18n_mutar.TestAplicabilidad"]
            fuera = subprocess.run(cmd, cwd=copia, capture_output=True, text=True,
                                   env={**os.environ, "I18N_MUTANDO": ""})
            dentro = subprocess.run(cmd, cwd=copia, capture_output=True, text=True,
                                    env={**os.environ, **mu.entorno_de_mutacion()})
            self.assertNotEqual(fuera.returncode, 0, "sin la marca, la aplicabilidad debe fallar")
            self.assertEqual(dentro.returncode, 0, dentro.stderr[-400:])


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
            return 0 if len(vistos) == 1 else 1  # sin mutar pasa; mutado falla => el mutante muere
        self.assertEqual(mu.ejecutar([m], self.raiz, correr), [])
        self.assertEqual(vistos, ["hola mundo\n", "adiós mundo\n"])
        with open(os.path.join(self.raiz, "f.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "hola mundo\n", "el original no se toca")

    def test_mutante_superviviente_si_el_runner_pasa(self):
        m = ("x", "f.txt", "hola", "adiós")
        self.assertEqual(mu.ejecutar([m], self.raiz, lambda copia: 0), ["x"])  # todo pasa => sobrevive

    def test_mutante_no_aplicable_cuenta_como_superviviente(self):
        m = ("y", "f.txt", "no existe", "z")
        self.assertEqual(mu.ejecutar([m], self.raiz, lambda copia: 0), ["y (no aplicable)"])

    def test_la_copia_mutada_conserva_el_git_para_contrastar_la_linea_base(self):
        """Sin .git, el test que contrasta la base con el commit se omite y los mutantes
        de PATRONES sobreviven (hallazgo m-5 de la revisión)."""
        os.makedirs(os.path.join(self.raiz, ".git"))
        with open(os.path.join(self.raiz, ".git", "HEAD"), "w") as f:
            f.write("ref: refs/heads/x\n")
        vistos = []
        mu.ejecutar([("x", "f.txt", "hola", "adiós")], self.raiz,
                    lambda copia: vistos.append(os.path.exists(os.path.join(copia, ".git", "HEAD"))) or 0)
        self.assertEqual(vistos, [True, True])

    def test_el_scratch_del_ejecutor_no_se_copia(self):
        os.makedirs(os.path.join(self.raiz, ".superpowers"))
        with open(os.path.join(self.raiz, ".superpowers", "x"), "w") as f:
            f.write("x")
        vistos = []
        mu.ejecutar([("x", "f.txt", "hola", "adiós")], self.raiz,
                    lambda copia: vistos.append(os.path.exists(os.path.join(copia, ".superpowers"))) or 0)
        self.assertEqual(vistos, [False, False])

    def test_si_la_suite_sin_mutar_no_pasa_la_herramienta_se_niega_a_medir(self):
        """Sin esta guarda, todo mutante «moriría» por un fallo que ya estaba (auto-muerte)."""
        with self.assertRaises(mu.SuiteSinMutarRoja):
            mu.ejecutar([("x", "f.txt", "hola", "adiós")], self.raiz, lambda copia: 1)

    def test_la_comprobacion_sin_mutar_se_hace_una_sola_vez(self):
        llamadas = []
        mu.ejecutar([("a", "f.txt", "hola", "adiós"), ("b", "f.txt", "mundo", "luna")], self.raiz,
                    lambda copia: llamadas.append(1) or (0 if len(llamadas) == 1 else 1))
        self.assertEqual(len(llamadas), 3)  # 1 sin mutar + 2 mutantes

    def test_exit_code_del_main(self):
        self.assertEqual(mu.codigo_de_salida([]), 0)
        self.assertEqual(mu.codigo_de_salida(["x"]), 1)


if __name__ == "__main__":
    unittest.main()
