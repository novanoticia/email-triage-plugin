"""El texto de cada catálogo está en su idioma (marcadores ortográficos)."""
import os
import re
import unittest

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage", "i18n")
_FUNC_ES = re.compile(r"\b(el|la|los|las|del|con|para|por|una|que|se|tu|sus|puede|correos?|bandeja|carpeta|hilo)\b", re.I)
_FUNC_ES_PARA_FR = re.compile(r"\b(el|los|las|del|con|para|por|una|sus|puede|correos?|bandeja|carpeta|hilo)\b", re.I)
_FUNC_EN_PARA_FR = re.compile(r"\b(the|your|you|with|from|and|of|inbox|emails?|folder|thread)\b", re.I)
_FUNC_FR = re.compile(r"\b(le|les|des|du|une|votre|vos|avec|dans|sont|boîte|dossier)\b", re.I)


def sin_codigo(texto):
    """Quita lo que va entre comillas invertidas: rutas y claves contractuales."""
    return re.sub(r"`[^`]*`", "", texto)


def cargar(cod):
    with open(os.path.join(DIR, cod + ".yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)["frases"]


class TestMarcadores(unittest.TestCase):
    @unittest.skip("heurística de palabras compartidas entre es/en/fr: no discrimina; "
                   "sustituida por marcadores ortográficos (abajo)")
    def test_palabras_comunes(self):
        pass

    def test_en_no_contiene_marcas_de_es_ni_fr(self):
        malas = []
        for k, d in cargar("en").items():
            if d.get("invariable"):
                continue
            t = d["texto"]
            if re.search(r"[¿¡ñ]", t) or re.search(r"[çèêàùôœ]", t):
                malas.append(k)
        self.assertEqual(malas, [], "en.yaml con ortografía de otro idioma")

    def test_en_sin_palabras_funcionales_de_es_ni_fr(self):
        """Una frase sin traducir (o a medias) se delata por palabras de otro idioma.

        Un test positivo («tiene alguna palabra inglesa») no sirve: las plantillas
        son estructurales y muchas frases correctas no llevan ninguna palabra común.
        """
        malas = [k for k, d in cargar("en").items()
                 if not d.get("invariable") and (_FUNC_ES.search(sin_codigo(d["texto"]))
                                                 or _FUNC_FR.search(sin_codigo(d["texto"])))]
        self.assertEqual(malas, [], "frases de en.yaml con palabras funcionales de es/fr")

    def test_el_detector_distingue_los_idiomas(self):
        self.assertTrue(_FUNC_ES.search("Resumen de la bandeja con los correos"))
        self.assertTrue(_FUNC_FR.search("Résumé des fils avec le dossier"))
        self.assertIsNone(_FUNC_ES.search("Summary of the inbox with the emails"))
        self.assertIsNone(_FUNC_FR.search("Summary of the inbox with the emails"))


class TestMarcadoresFr(unittest.TestCase):
    def test_fr_sin_palabras_funcionales_de_es_ni_en(self):
        malas = [k for k, d in cargar("fr").items()
                 if not d.get("invariable") and (_FUNC_ES_PARA_FR.search(sin_codigo(d["texto"]))
                                                 or _FUNC_EN_PARA_FR.search(sin_codigo(d["texto"])))]
        self.assertEqual(malas, [], "frases de fr.yaml con palabras funcionales de es/en")

    def test_fr_no_lleva_signos_espanoles(self):
        malas = [k for k, d in cargar("fr").items() if re.search(r"[¿¡ñ]", d["texto"])]
        self.assertEqual(malas, [])

    def test_fr_usa_ortografia_francesa_en_el_catalogo(self):
        con_marcas = [k for k, d in cargar("fr").items() if re.search(r"[çèêàùôœéî]", d["texto"])]
        self.assertGreaterEqual(len(con_marcas), 60, "pocas frases con acentos franceses")

    def test_tipografia_francesa_espacio_antes_de_interrogacion(self):
        malas = [k for k, d in cargar("fr").items() if re.search(r"[^\s\u00a0\u202f]\?", d["texto"])]
        self.assertEqual(malas, [], "en francés va un espacio antes de «?»")

    def test_tipografia_francesa_espacio_antes_de_dos_puntos_en_etiquetas(self):
        # etiquetas «Texto : valor»; se excluyen horas HH:MM:SS, rutas y URL
        malas = [k for k, d in cargar("fr").items()
                 if re.search(r"[A-Za-zÀ-ÿ\]\)]:\s", d["texto"])]
        self.assertEqual(malas, [], "en francés va un espacio antes de «:»")

    def test_comillas_francesas_en_lugar_de_rectas(self):
        malas = [k for k, d in cargar("fr").items() if '"' in d["texto"]]
        self.assertEqual(malas, [], "usa « » en fr.yaml")


class TestEstadoVigilado(unittest.TestCase):
    """Una afirmación de estado en la documentación debe estar vigilada por una prueba."""
    AFIRMACION = "ninguna traducción está revisada"

    def estados(self):
        out = {}
        for cod in ("en", "fr"):
            with open(os.path.join(DIR, cod + ".yaml"), encoding="utf-8") as f:
                out[cod] = yaml.safe_load(f)
        return out

    def test_sin_revisor_nadie_figura_revisado(self):
        for cod, doc in self.estados().items():
            if not doc.get("revisado_por"):
                self.assertNotEqual(doc["estado"], "revisado", cod)

    def test_la_afirmacion_del_readme_se_retira_si_algun_idioma_se_revisa(self):
        hay_revisado = any(d["estado"] == "revisado" for d in self.estados().values())
        with open(os.path.join(RAIZ, "README.md"), encoding="utf-8") as f:
            readme = " ".join(f.read().lower().split())  # el README reflujea las frases
        if hay_revisado:
            self.assertNotIn(self.AFIRMACION, readme,
                             "algún catálogo está revisado: retira la afirmación del README")


if __name__ == "__main__":
    unittest.main()
