"""Extracción de literales con herramienta (no a mano) y cobertura."""
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import i18n_extraer as ex  # noqa: E402

SKILL = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage")


class TestExtraerSintetico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = self.tmp.name
        os.makedirs(os.path.join(self.raiz, ex.SKILL_REL))
        with open(os.path.join(self.raiz, ex.SKILL_REL, "A.md"), "w", encoding="utf-8") as f:
            f.write("uno\n📬 [Asunto]\n> cita 1\n> cita 2\nrepetida\nrepetida\n")

    def tearDown(self):
        self.tmp.cleanup()

    def man(self, patron, **extra):
        return {"frases": [dict(clave="k", fichero="A.md", patron=patron, **extra)],
                "excluidos": [], "nuevas": []}

    def test_lee_el_literal_real_y_su_linea(self):
        r = ex.extraer(self.man(r"^(📬 \[Asunto\])$"), self.raiz)
        self.assertEqual(r["k"]["texto"], "📬 [Asunto]")
        self.assertEqual(r["k"]["fuente"], "A.md:2")

    def test_cita_quita_el_prefijo(self):
        r = ex.extraer(self.man(r"(?s)^(> cita 1\n> cita 2)$", cita=True), self.raiz)
        self.assertEqual(r["k"]["texto"], "cita 1\ncita 2")

    def test_cero_coincidencias_falla(self):
        with self.assertRaisesRegex(ex.ErrorExtraccion, "k.*0 coincidencias"):
            ex.extraer(self.man(r"^(no existe)$"), self.raiz)

    def test_varias_coincidencias_falla(self):
        with self.assertRaisesRegex(ex.ErrorExtraccion, "k.*2 coincidencias"):
            ex.extraer(self.man(r"^(repetida)$"), self.raiz)

    def test_patron_sin_grupo_falla(self):
        with self.assertRaisesRegex(ex.ErrorExtraccion, "grupo"):
            ex.extraer(self.man(r"^uno$"), self.raiz)

    def test_clave_duplicada_falla(self):
        m = self.man(r"^(uno)$")
        m["frases"].append(dict(m["frases"][0]))
        with self.assertRaisesRegex(ex.ErrorExtraccion, "duplicada"):
            ex.extraer(m, self.raiz)

    def test_plano_une_las_lineas_de_una_frase_reflujada(self):
        with open(os.path.join(self.raiz, ex.SKILL_REL, "B.md"), "w", encoding="utf-8") as f:
            f.write('   di: "Hola mundo, esto\n   sigue aquí\n   y termina?" fin\n')
        m = {"frases": [dict(clave="q", fichero="B.md", plano=True,
                             patron=r'(?s)"(Hola mundo.*?termina\?)"')],
             "excluidos": [], "nuevas": []}
        self.assertEqual(ex.extraer(m, self.raiz)["q"]["texto"],
                         "Hola mundo, esto sigue aquí y termina?")

    def test_las_lineas_se_cuentan_sin_los_bloques_i18n(self):
        """La fuente apunta al original: un bloque añadido no la desplaza ni cuenta como literal."""
        with open(os.path.join(self.raiz, ex.SKILL_REL, "C.md"), "w", encoding="utf-8") as f:
            f.write("uno\n\n<!-- i18n:inicio -->\nbloque\n📬 [Asunto]\n<!-- i18n:fin -->\n\n📬 [Asunto]\n")
        m = {"frases": [dict(clave="k", fichero="C.md", patron=r"^(📬 \[Asunto\])$")],
             "excluidos": [], "nuevas": []}
        self.assertEqual(ex.extraer(m, self.raiz)["k"]["fuente"], "C.md:3")

    def test_sin_bloques_i18n_quita_el_bloque_y_un_blanco(self):
        self.assertEqual(ex.sin_bloques_i18n("a\n\n<!-- i18n:inicio -->\nx\n<!-- i18n:fin -->\n\nb"),
                         "a\n\nb")

    def test_claves_nuevas_marcadas_origen_nuevo(self):
        m = self.man(r"^(uno)$")
        m["nuevas"] = [{"clave": "aviso.x", "texto": "hola"}]
        r = ex.extraer(m, self.raiz)
        self.assertEqual((r["aviso.x"]["origen"], r["aviso.x"]["fuente"]),
                         ("nuevo", "manifiesto"))
        self.assertEqual(r["k"]["origen"], "original")

    def test_clave_nueva_no_puede_repetir_una_original(self):
        m = self.man(r"^(uno)$")
        m["nuevas"] = [{"clave": "k", "texto": "hola"}]
        with self.assertRaisesRegex(ex.ErrorExtraccion, "duplicada"):
            ex.extraer(m, self.raiz)


class TestLineasVisibles(unittest.TestCase):
    def test_detecta_bloque_sin_lenguaje_y_citas_y_omite_bash(self):
        md = "texto\n```\nlinea A\n```\n```bash\nls\n```\n> cita\n"
        self.assertEqual(ex.lineas_visibles(md), [(3, "linea A"), (8, "> cita")])


class TestLineasVisiblesIndentadas(unittest.TestCase):
    def test_bloque_con_fence_indentado_dentro_de_una_lista(self):
        md = "1. paso\n   ```\n   Voy a revertir\n   ```\n   ```bash\n   ls\n   ```\n"
        self.assertEqual(ex.lineas_visibles(md), [(3, "   Voy a revertir")])


class TestTambien(unittest.TestCase):
    def test_la_misma_linea_en_otro_fichero_queda_cubierta(self):
        man = {"frases": [{"clave": "k", "fichero": "A.md", "patron": r"^(hola)$",
                           "tambien": ["B.md"]}], "excluidos": [], "nuevas": []}
        self.assertEqual(ex.lineas_cubiertas(man, "B.md", "x\nhola\n"), {2})
        self.assertEqual(ex.lineas_cubiertas(man, "C.md", "x\nhola\n"), set())


class TestEsYaml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.man = ex.cargar_manifiesto(os.path.join(RAIZ, "scripts", "i18n_fuentes.yaml"))
        cls.frases = ex.extraer(cls.man, RAIZ)

    def test_todo_literal_existe_en_el_original(self):
        for clave, d in self.frases.items():
            if d["origen"] == "nuevo":
                continue
            fichero = d["fuente"].rsplit(":", 1)[0]
            with open(os.path.join(SKILL, fichero), encoding="utf-8") as f:
                original = ex.sin_bloques_i18n(f.read())
            plano = " ".join(original.split())
            for l in d["texto"].split("\n"):
                self.assertIn(" ".join(l.split()), plano, clave)

    def test_cobertura_toda_linea_visible_esta_clasificada(self):
        """Cada línea de plantilla visible es un literal con clave o está excluida."""
        sin_clasificar = []
        for rel in sorted({f["fichero"] for f in self.man["frases"]}
                          | {e["fichero"] for e in self.man["excluidos"]}
                          | ex.FICHEROS_VISIBLES):
            with open(os.path.join(SKILL, rel), encoding="utf-8") as f:
                texto = ex.sin_bloques_i18n(f.read())
            cubiertas = ex.lineas_cubiertas(self.man, rel, texto)
            for n, linea in ex.lineas_visibles(texto):
                if not linea.strip() or n in cubiertas:
                    continue
                sin_clasificar.append(f"{rel}:{n}: {linea[:70]}")
        self.assertEqual(sin_clasificar, [], "líneas visibles sin clave ni exclusión")

    def test_es_yaml_en_disco_coincide_con_la_extraccion(self):
        import yaml
        with open(os.path.join(SKILL, "i18n", "es.yaml"), encoding="utf-8") as f:
            es = yaml.safe_load(f)
        self.assertEqual(es["estado"], "referencia")
        self.assertEqual({k: v["texto"] for k, v in es["frases"].items()},
                         {k: v["texto"] for k, v in self.frases.items()})

    def test_riesgo_alto_en_las_frases_que_confirman_acciones(self):
        for k in ("correo.recomendacion", "lote.confirmar", "deshacer.confirmar"):
            self.assertEqual(self.frases[k]["riesgo"], "alto", k)


if __name__ == "__main__":
    unittest.main()
