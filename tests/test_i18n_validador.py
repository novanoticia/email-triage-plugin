"""El validador de verdad falla: un catálogo roto por cada regla."""
import copy
import os
import sys
import tempfile
import unittest

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import i18n_validar as v  # noqa: E402

SKILL = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage")


def fr(texto, **kw):
    d = {"texto": texto, "origen": "original", "fuente": "x:1", "riesgo": "normal",
         "lista": False, "invariable": False}
    d.update(kw)
    return d


ES = {"estado": "referencia", "redactado_por": "x", "revisado_por": "yo", "frases": {
    "a": fr("📥 Bandeja de entrada: X correos revisados"),
    "b": fr("🔵 Recomendación: MOVER → [destino] / DEJAR / ARCHIVAR", riesgo="alto", lista=True),
    "c": fr("- `🔴 REPLY_NEEDED` — rojo"),
}}
EN = {"estado": "borrador-ia", "redactado_por": "IA", "revisado_por": None, "frases": {
    "a": fr("📥 Inbox: X emails reviewed"),
    "b": fr("🔵 Recommendation: MOVE → [destination] / LEAVE / ARCHIVE", riesgo="alto", lista=True),
    "c": fr("- `🔴 REPLY_NEEDED` — red"),
}}
GLOS = {"terminos": [{"es": "bandeja de entrada", "en": "inbox"},
                     {"es": "correo", "en": "email"}]}


class Base(unittest.TestCase):
    def validar(self, en=None, es=None, glos=None):
        with tempfile.TemporaryDirectory() as d:
            for nombre, doc in (("es", es or ES), ("en", en or EN), ("glosario", glos or GLOS)):
                with open(os.path.join(d, nombre + ".yaml"), "w", encoding="utf-8") as f:
                    yaml.safe_dump(doc, f, allow_unicode=True)
            return v.validar(d)

    def en_modificado(self, fn):
        en = copy.deepcopy(EN)
        fn(en)
        return en

    def assertError(self, errores, fragmento):
        self.assertTrue(any(fragmento in e for e in errores), f"{fragmento!r} no está en {errores}")


class TestCatalogoValido(Base):
    def test_el_par_sano_no_da_errores(self):
        self.assertEqual(self.validar(), [])


class TestReglas(Base):
    def test_clave_que_falta(self):
        e = self.validar(en=self.en_modificado(lambda d: d["frases"].pop("c")))
        self.assertError(e, "falta la clave c")

    def test_clave_sobrante(self):
        e = self.validar(en=self.en_modificado(lambda d: d["frases"].update(z=fr("hola"))))
        self.assertError(e, "clave z no existe en es")

    def test_texto_vacio(self):
        e = self.validar(en=self.en_modificado(lambda d: d["frases"]["a"].update(texto="  ")))
        self.assertError(e, "texto vacío")

    def test_texto_vacio_en_es(self):
        es = copy.deepcopy(ES)
        es["frases"]["a"]["texto"] = ""
        self.assertError(self.validar(es=es), "es.a: texto vacío")

    def test_todo_en_el_texto(self):
        e = self.validar(en=self.en_modificado(
            lambda d: d["frases"]["a"].update(texto="📥 Inbox TODO email")))
        self.assertError(e, "TODO")

    def test_contractual_entre_comillas_invertidas_cambiado(self):
        e = self.validar(en=self.en_modificado(
            lambda d: d["frases"]["c"].update(texto="- `🔴 REPLY NEEDED` — red")))
        self.assertError(e, "contractual")

    def test_tier_traducido(self):
        e = self.validar(en=self.en_modificado(
            lambda d: d["frases"]["c"].update(texto="- `🔴 REPLY_NEEDED` — red REVIEW")))
        self.assertError(e, "tiers")

    def test_emoji_distinto(self):
        e = self.validar(en=self.en_modificado(
            lambda d: d["frases"]["a"].update(texto="📤 Inbox: X emails reviewed")))
        self.assertError(e, "emojis")

    def test_hueco_entre_corchetes_distinto(self):
        e = self.validar(en=self.en_modificado(lambda d: d["frases"]["b"].update(
            texto="🔵 Recommendation: MOVE → destination / LEAVE / ARCHIVE")))
        self.assertError(e, "huecos")

    def test_lista_con_distinto_numero_de_opciones(self):
        e = self.validar(en=self.en_modificado(lambda d: d["frases"]["b"].update(
            texto="🔵 Recommendation: MOVE → [destination] / LEAVE")))
        self.assertError(e, "opciones")

    def test_texto_igual_al_original_sin_invariable(self):
        e = self.validar(en=self.en_modificado(lambda d: d["frases"]["a"].update(
            texto=ES["frases"]["a"]["texto"])))
        self.assertError(e, "idéntico al original")

    def test_texto_igual_al_original_con_invariable_es_valido(self):
        e = self.validar(en=self.en_modificado(lambda d: d["frases"]["c"].update(
            texto=ES["frases"]["c"]["texto"], invariable=True)))
        self.assertEqual(e, [])

    def test_revisado_sin_revisor(self):
        e = self.validar(en=self.en_modificado(lambda d: d.update(estado="revisado")))
        self.assertError(e, "sin revisor")

    def test_estado_desconocido(self):
        e = self.validar(en=self.en_modificado(lambda d: d.update(estado="ok")))
        self.assertError(e, "estado")

    def test_ia_no_puede_figurar_como_revisor(self):
        e = self.validar(en=self.en_modificado(
            lambda d: d.update(estado="revisado", revisado_por="IA")))
        self.assertError(e, "revisor")

    def test_revisor_humano_es_valido(self):
        e = self.validar(en=self.en_modificado(
            lambda d: d.update(estado="revisado", revisado_por="Ana García")))
        self.assertEqual(e, [])

    def test_riesgo_alto_perdido(self):
        e = self.validar(en=self.en_modificado(lambda d: d["frases"]["b"].update(riesgo="normal")))
        self.assertError(e, "riesgo")

    def test_glosario_no_aplicado(self):
        e = self.validar(en=self.en_modificado(
            lambda d: d["frases"]["a"].update(texto="📥 Mailbox: X emails reviewed")))
        self.assertError(e, "glosario")

    def test_yaml_ilegible(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("es", "glosario"):
                with open(os.path.join(d, n + ".yaml"), "w", encoding="utf-8") as f:
                    yaml.safe_dump(ES if n == "es" else GLOS, f, allow_unicode=True)
            with open(os.path.join(d, "en.yaml"), "w", encoding="utf-8") as f:
                f.write("frases: [sin cerrar")
            self.assertError(v.validar(d), "no se pudo leer")

    def test_estructura_sin_frases(self):
        with tempfile.TemporaryDirectory() as d:
            for n, doc in (("es", ES), ("en", {"estado": "borrador-ia", "frases": ["x"]})):
                with open(os.path.join(d, n + ".yaml"), "w", encoding="utf-8") as f:
                    yaml.safe_dump(doc, f, allow_unicode=True)
            self.assertError(v.validar(d), "estructura inválida")

    def test_glosario_ilegible(self):
        with tempfile.TemporaryDirectory() as d:
            for n, doc in (("es", ES), ("en", EN)):
                with open(os.path.join(d, n + ".yaml"), "w", encoding="utf-8") as f:
                    yaml.safe_dump(doc, f, allow_unicode=True)
            with open(os.path.join(d, "glosario.yaml"), "w", encoding="utf-8") as f:
                f.write("terminos: [sin cerrar")
            self.assertError(v.validar(d), "glosario.yaml: no se pudo leer")

    def test_sin_es_yaml(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "en.yaml"), "w", encoding="utf-8") as f:
                yaml.safe_dump(EN, f, allow_unicode=True)
            self.assertError(v.validar(d), "falta es.yaml")

    def test_glosario_no_se_trata_como_idioma(self):
        # glosario.yaml no tiene `frases`: si se validara como catálogo daría error
        self.assertEqual(self.validar(), [])


class TestCatalogosReales(Base):
    def test_los_catalogos_del_repositorio_son_validos(self):
        self.assertEqual(v.validar(os.path.join(SKILL, "i18n")), [])

    def test_es_es_la_referencia(self):
        with open(os.path.join(SKILL, "i18n", "es.yaml"), encoding="utf-8") as f:
            self.assertEqual(yaml.safe_load(f)["estado"], "referencia")

    IDIOMAS_ESPERADOS = ("es", "en", "fr")

    def test_claves_de_entrada_y_avisos_existen_en_todos(self):
        for cod in self.IDIOMAS_ESPERADOS:
            with open(os.path.join(SKILL, "i18n", cod + ".yaml"), encoding="utf-8") as f:
                claves = yaml.safe_load(f)["frases"].keys()
            for k in ("entrada.afirmativo", "entrada.negativo", "aviso.ia",
                      "aviso.idioma_desconocido", "aviso.respaldo"):
                self.assertIn(k, claves, f"{cod}.yaml sin {k}")

    def test_glosario_real_cubre_los_idiomas_soportados(self):
        with open(os.path.join(SKILL, "i18n", "glosario.yaml"), encoding="utf-8") as f:
            terminos = yaml.safe_load(f)["terminos"]
        self.assertGreaterEqual(len(terminos), 6)
        for t in terminos:
            for cod in ("es", "en", "fr"):
                self.assertTrue(str(t.get(cod, "")).strip(), f"{t} sin {cod}")


if __name__ == "__main__":
    unittest.main()
