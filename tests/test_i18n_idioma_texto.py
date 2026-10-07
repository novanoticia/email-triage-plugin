"""El texto de cada catálogo está en su idioma (marcadores ortográficos)."""
import os
import re
import unittest

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage", "i18n")
_FUNC_ES = re.compile(r"\b(el|la|los|las|del|con|para|por|una|que|se|tu|sus|puede|correos?|bandeja|carpeta|hilo)\b", re.I)
_FUNC_FR = re.compile(r"\b(le|les|des|du|une|votre|vos|avec|dans|sont|boîte|dossier)\b", re.I)


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
                 if not d.get("invariable") and (_FUNC_ES.search(d["texto"])
                                                 or _FUNC_FR.search(d["texto"]))]
        self.assertEqual(malas, [], "frases de en.yaml con palabras funcionales de es/fr")

    def test_el_detector_distingue_los_idiomas(self):
        self.assertTrue(_FUNC_ES.search("Resumen de la bandeja con los correos"))
        self.assertTrue(_FUNC_FR.search("Résumé des fils avec le dossier"))
        self.assertIsNone(_FUNC_ES.search("Summary of the inbox with the emails"))
        self.assertIsNone(_FUNC_FR.search("Summary of the inbox with the emails"))


if __name__ == "__main__":
    unittest.main()
