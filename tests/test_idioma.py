"""Regla única de selección del idioma (spec §3): una prueba por fila."""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)
import tests  # noqa: E402,F401  (pone scripts/ en sys.path)
import idioma  # noqa: E402

SCRIPT = os.path.join(tests.DIR_SCRIPTS, "idioma.py")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        for cod in ("es", "en", "fr"):
            open(os.path.join(self.dir, cod + ".yaml"), "w").close()
        open(os.path.join(self.dir, "glosario.yaml"), "w").close()  # no es un idioma

    def tearDown(self):
        self.tmp.cleanup()

    def r(self, args, cfg=None):
        return idioma.resolver(args, cfg, self.dir)

    def motivos(self, res):
        return [a["motivo"] for a in res["avisos"]]


class TestMarca(Base):
    def test_idioma_igual_en(self):
        res = self.r("filtra mi correo idioma=en")
        self.assertEqual((res["idioma"], res["origen"], res["avisos"]), ("en", "marca", []))

    def test_lang_igual_fr(self):
        self.assertEqual(self.r("lang=fr dry-run")["idioma"], "fr")

    def test_mayusculas_y_locale(self):
        for crudo, esperado in [("EN", "en"), ("en-US", "en"), ("fr_FR.UTF-8", "fr"),
                                ("IDIOMA=FR", "fr")]:
            with self.subTest(crudo=crudo):
                arg = crudo if crudo.startswith("IDIOMA") else f"idioma={crudo}"
                self.assertEqual(self.r(arg)["idioma"], esperado)

    def test_es_explicito(self):
        res = self.r("idioma=es")
        self.assertEqual((res["idioma"], res["origen"], res["avisos"]), ("es", "marca", []))

    def test_puntuacion_y_comillas_pegadas(self):  # Review Focus 2
        for arg in ("idioma=en.", "idioma=en,", 'idioma="fr"', "(idioma=fr)", "idioma=en!"):
            with self.subTest(arg=arg):
                res = self.r(arg)
                self.assertIn(res["idioma"], ("en", "fr"))
                self.assertEqual(res["avisos"], [])

    def test_codigo_sin_catalogo(self):
        res = self.r("idioma=de")
        self.assertEqual(res["idioma"], "es")
        self.assertEqual(self.motivos(res), ["desconocido"])
        self.assertEqual(res["disponibles"], ["en", "es", "fr"])

    def test_vacio(self):
        for arg in ("idioma=", "revisa idioma= la bandeja"):
            with self.subTest(arg=arg):
                res = self.r(arg)
                self.assertEqual((res["idioma"], self.motivos(res)), ("es", ["vacio"]))

    def test_forma_invalida(self):
        for arg in ("idioma=xx1", "idioma=español", "idioma=e", "idioma=."):
            with self.subTest(arg=arg):
                res = self.r(arg)
                self.assertEqual((res["idioma"], self.motivos(res)), ("es", ["forma"]))

    def test_marca_repetida_gana_la_primera_y_avisa(self):
        res = self.r("idioma=en idioma=fr")
        self.assertEqual((res["idioma"], self.motivos(res)), ("en", ["repetida"]))

    def test_primera_invalida_no_se_salta(self):
        res = self.r("idioma=de idioma=fr")
        self.assertEqual(res["idioma"], "es")
        self.assertEqual(self.motivos(res), ["desconocido", "repetida"])


class TestSinMarca(Base):
    def test_codigo_suelto_no_es_marca(self):
        for arg in ("filtra en Leer Después", "es", "en", "triaje en fr", "dry-run"):
            with self.subTest(arg=arg):
                res = self.r(arg)
                self.assertEqual((res["idioma"], res["origen"], res["avisos"]),
                                 ("es", "defecto", []))

    def test_palabra_pegada_no_es_marca(self):
        self.assertEqual(self.r("xidioma=fr")["origen"], "defecto")

    def test_config_valida(self):
        res = self.r("revisa mi bandeja", "fr")
        self.assertEqual((res["idioma"], res["origen"]), ("fr", "config"))

    def test_config_vacia_o_ausente_es_defecto(self):  # Review Focus 3
        for cfg in (None, "", "   "):
            with self.subTest(cfg=cfg):
                res = self.r("hola", cfg)
                self.assertEqual((res["idioma"], res["origen"], res["avisos"]),
                                 ("es", "defecto", []))

    def test_config_invalida_avisa(self):  # Review Focus 3
        for cfg, motivo in (("de", "desconocido"), ("español", "forma")):
            with self.subTest(cfg=cfg):
                res = self.r("hola", cfg)
                self.assertEqual((res["idioma"], self.motivos(res)), ("es", [motivo]))

    def test_la_marca_gana_a_la_config(self):
        self.assertEqual(self.r("idioma=en", "fr")["idioma"], "en")

    def test_config_no_texto(self):
        for cfg in (5, ["fr"], {"a": 1}):
            with self.subTest(cfg=cfg):
                self.assertEqual(self.r("hola", cfg)["idioma"], "es")


class TestDisponibles(Base):
    def test_autodescubre_y_excluye_glosario(self):
        self.assertEqual(idioma.disponibles(self.dir), ["en", "es", "fr"])

    def test_idioma_nuevo_se_descubre_soltando_un_fichero(self):
        open(os.path.join(self.dir, "pt.yaml"), "w").close()
        self.assertEqual(self.r("idioma=pt")["idioma"], "pt")

    def test_codigo_de_tres_letras_valido_y_de_cuatro_no(self):
        open(os.path.join(self.dir, "fil.yaml"), "w").close()
        self.assertEqual(self.r("idioma=fil")["idioma"], "fil")
        res = self.r("idioma=abcd")
        self.assertEqual((res["idioma"], self.motivos(res)), ("es", ["forma"]))

    def test_directorio_inexistente_degrada_a_es(self):
        self.assertEqual(idioma.disponibles(os.path.join(self.dir, "nada")), ["es"])


class TestTotalidad(Base):
    def test_fuzz_nunca_lanza_y_devuelve_dict_serializable(self):
        rng = random.Random(20261007)
        trozos = ["idioma=", "lang=", "en", "FR", "-", "_", ".", " ", "\n", "é",
                  "'", '"', "es", "idioma=en", "\x00", "🙂", "=", ","]
        for _ in range(5000):
            txt = "".join(rng.choice(trozos) for _ in range(rng.randint(0, 12)))
            cfg = rng.choice([None, "", "fr", txt, 3])
            res = idioma.resolver(txt, cfg, self.dir)
            self.assertIsInstance(res, dict)
            json.dumps(res, ensure_ascii=False)

    def test_entradas_no_texto(self):
        for arg in (None, 5, [], {}):
            self.assertEqual(self.r(arg)["idioma"], "es")


class TestCLI(Base):
    def run_cli(self, entrada):
        p = subprocess.run([sys.executable, SCRIPT, "resolver", "--i18n", self.dir],
                           input=entrada, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_cli_resuelve(self):
        res = self.run_cli(json.dumps({"argumentos": "idioma=fr", "config_idioma": "es"}))
        self.assertEqual(res["idioma"], "fr")

    def test_cli_con_basura_degrada_pero_avisa(self):
        """Hallazgo I-3 de la revisión: un JSON roto NO puede degradar a `es` en silencio."""
        for entrada in ("no es json", "[1,2]", "5", '{"argumentos": "dis "bonjour" idioma=fr"}'):
            with self.subTest(entrada=entrada):
                res = self.run_cli(entrada)
                self.assertEqual(res["idioma"], "es")
                self.assertEqual(self.motivos(res), ["entrada_invalida"])

    def test_cli_con_entrada_vacia_no_avisa(self):
        res = self.run_cli("")
        self.assertEqual((res["idioma"], res["avisos"]), ("es", []))

    def run_texto(self, mensaje, *extra):
        p = subprocess.run([sys.executable, SCRIPT, "resolver", "--texto", "--i18n", self.dir, *extra],
                           input=mensaje, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_modo_texto_acepta_apostrofos_y_comillas(self):
        """El mensaje va en bruto por stdin (desde un fichero): en francés el apóstrofo es habitual."""
        for msg in ("j'aimerais voir idioma=fr", 'dis "bonjour" idioma=fr',
                    "l'été, \"oui\", idioma=fr\nsegunda línea", "idioma=fr $(whoami) `id` \\"):
            with self.subTest(msg=msg):
                res = self.run_texto(msg)
                self.assertEqual((res["idioma"], res["origen"], res["avisos"]), ("fr", "marca", []))

    def test_modo_texto_sin_marca_usa_la_config(self):
        res = self.run_texto("revisa mi bandeja", "--config-idioma", "fr")
        self.assertEqual((res["idioma"], res["origen"]), ("fr", "config"))

    def test_modo_texto_vacio_y_sin_config_es_el_defecto(self):
        res = self.run_texto("")
        self.assertEqual((res["idioma"], res["origen"], res["avisos"]), ("es", "defecto", []))

    def test_modo_texto_json_no_se_interpreta(self):
        res = self.run_texto('{"config_idioma": "fr"}')
        self.assertEqual(res["origen"], "defecto")  # en modo texto el JSON es solo texto


if __name__ == "__main__":
    unittest.main()
