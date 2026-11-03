"""remitentes_lectura (v3.28.0): un autor que se lee sin prisa sale en
READING_LATER, ni más arriba ni más abajo.

Dry-runs reales del 2026-11-03: los ensayos de autores que se siguen subían a
REVIEW con el principal y bajaban a ARCHIVE con los evaluadores externos; la
medición 26 (banco lector, Gemini) los repartió entre −9 y +5. Decisiones
D1-D7 de docs/diseno-remitentes-lectura.md. Sin la lista, nada cambia. Sin red.
"""
import copy
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

if DIR_SCRIPTS not in sys.path:
    sys.path.insert(0, DIR_SCRIPTS)
import triage_helpers as th  # noqa: E402

CFG = {
    "criterios_epistemicos": {
        "a": {"activo": True, "core": True, "eje": "valor_decisional",
              "si": 6, "no": -5}},
    "scoring": {"ejes": {"valor_decisional": [-10, 10]}},
    "tiers": {"reply_needed": 10, "review": 4, "reading_later": 0,
              "archive": -1},
    "hard_rules": {"sender_bulk_penalizacion": -4,
                   "deadline_explicito_boost": 4,
                   "pregunta_directa_boost": 4},
    "filtros": {"remitentes_prioritarios": [],
                "remitentes_lectura": ["autora@boletin.example",
                                       "@ensayos.example"]},
}
AUTORA = "Autora <autora@boletin.example>"
# Ensayo que el evaluador sube a REVIEW (6) y otro que baja a ARCHIVE (−9).
ALTO = {"verdicts": {"a": "si"}}
BAJO = {"verdicts": {"a": "no"}, "hard_rules": ["sender_bulk_penalizacion"]}


def _p(base, **extra):
    p = copy.deepcopy(base)
    p.update(extra)
    return p


def _sin_lista():
    c = copy.deepcopy(CFG)
    del c["filtros"]["remitentes_lectura"]
    return c


class TestTechoYSuelo(unittest.TestCase):
    """D1: suelo y techo; D3: el score no cambia."""

    def test_sin_la_lista_nada_cambia(self):
        for cfg in (_sin_lista(), dict(CFG, filtros={"remitentes_lectura": []})):
            r = th.cmd_scoring(_p(ALTO, remitente=AUTORA), cfg)
            self.assertEqual(r["tier"], "REVIEW")
            for k in ("remitente_lectura", "lectura_aplicada", "lectura_sin_techo"):
                self.assertNotIn(k, r)

    def test_techo(self):
        r = th.cmd_scoring(_p(ALTO, remitente=AUTORA), CFG)
        self.assertEqual(r["tier"], "READING_LATER")
        self.assertEqual(r["lectura_aplicada"],
                         "REVIEW->READING_LATER (remitente de lectura)")
        self.assertEqual(r["score"], 6)          # D3: el score no se toca
        self.assertTrue(r["remitente_lectura"])

    def test_suelo(self):
        r = th.cmd_scoring(_p(BAJO, remitente=AUTORA), CFG)
        self.assertEqual(r["tier"], "READING_LATER")
        self.assertEqual(r["lectura_aplicada"],
                         "ARCHIVE->READING_LATER (remitente de lectura)")
        self.assertEqual(r["score"], -9)

    def test_ya_en_reading_later_no_anota_cambio(self):
        r = th.cmd_scoring(_p(ALTO, remitente=AUTORA, extra_points=-4), CFG)
        self.assertEqual((r["tier"], r["score"]), ("READING_LATER", 2))
        self.assertNotIn("lectura_aplicada", r)
        self.assertTrue(r["remitente_lectura"])

    def test_otro_remitente_no_se_toca(self):
        r = th.cmd_scoring(_p(ALTO, remitente="otra@boletin.example"), CFG)
        self.assertEqual(r["tier"], "REVIEW")
        self.assertIs(r["remitente_lectura"], False)
        self.assertNotIn("lectura_aplicada", r)

    def test_sin_remitente_util_no_se_aplica(self):
        """Lo decide el script por el remitente: sin dirección, None y el
        tier de siempre (el modelo no puede aplicarlo a mano)."""
        for p in (_p(ALTO), _p(ALTO, remitente="Autora"), _p(ALTO, remitente=7)):
            r = th.cmd_scoring(p, CFG)
            self.assertEqual(r["tier"], "REVIEW")
            self.assertIsNone(r["remitente_lectura"])

    def test_sufijo_y_subdominio(self):
        for rem in ("autora+ensayos@boletin.example", "Autora <AUTORA@boletin.example>",
                    "x@news.ensayos.example", "y@ensayos.example"):
            r = th.cmd_scoring(_p(ALTO, remitente=rem), CFG)
            self.assertEqual(r["tier"], "READING_LATER", rem)
        # Un dominio que solo acaba igual no es un subdominio.
        r = th.cmd_scoring(_p(ALTO, remitente="z@noensayos.example"), CFG)
        self.assertEqual(r["tier"], "REVIEW")


class TestQueRompeElTecho(unittest.TestCase):
    """D2: F y D levantan el techo; P no; el cap por inyección manda."""

    def test_forzar_reply_needed(self):
        r = th.cmd_scoring(_p(ALTO, remitente=AUTORA, forzar_reply_needed=True), CFG)
        self.assertEqual(r["tier"], "REPLY_NEEDED")
        self.assertEqual(r["lectura_sin_techo"], ["forzar_reply_needed"])
        self.assertNotIn("lectura_aplicada", r)

    def test_deadline(self):
        r = th.cmd_scoring(_p(ALTO, remitente=AUTORA,
                              hard_rules=["deadline_explicito_boost"]), CFG)
        self.assertEqual((r["tier"], r["score"]), ("REVIEW", 10))
        self.assertEqual(r["lectura_sin_techo"], ["deadline_explicito_boost"])

    def test_deadline_no_quita_el_suelo(self):
        r = th.cmd_scoring(_p(BAJO, remitente=AUTORA, hard_rules=[
            "sender_bulk_penalizacion", "deadline_explicito_boost"]), CFG)
        self.assertEqual((r["tier"], r["score"]), ("READING_LATER", -5))
        self.assertIn("lectura_aplicada", r)

    def test_deadline_que_no_se_aplica_no_cuenta(self):
        """Una hard rule que el config no define no se suma, y tampoco abre."""
        cfg = copy.deepcopy(CFG)
        del cfg["hard_rules"]["deadline_explicito_boost"]
        r = th.cmd_scoring(_p(ALTO, remitente=AUTORA,
                              hard_rules=["deadline_explicito_boost"]), cfg)
        self.assertEqual(r["tier"], "READING_LATER")
        self.assertNotIn("lectura_sin_techo", r)

    def test_pregunta_directa_no_rompe(self):
        r = th.cmd_scoring(_p(ALTO, remitente=AUTORA,
                              hard_rules=["pregunta_directa_boost"]), CFG)
        self.assertEqual((r["tier"], r["score"]), ("READING_LATER", 10))
        self.assertNotIn("lectura_sin_techo", r)

    def test_el_cap_por_inyeccion_manda(self):
        r = th.cmd_scoring(_p(ALTO, remitente=AUTORA, forzar_reply_needed=True,
                              tier_maximo="REVIEW"), CFG)
        self.assertEqual(r["tier"], "REVIEW")
        r = th.cmd_scoring(_p(BAJO, remitente=AUTORA, tier_maximo="ARCHIVE"), CFG)
        self.assertEqual(r["tier"], "ARCHIVE")


class TestPrioritarios(unittest.TestCase):
    """D4: si un remitente está en las dos listas, manda remitentes_lectura."""

    def _cfg(self):
        c = copy.deepcopy(CFG)
        c["filtros"]["remitentes_prioritarios"] = ["autora@boletin.example"]
        c["filtros"]["suelo_prioritarios"] = "REVIEW"
        return c

    def test_scoring_sin_suelo_de_prioritario(self):
        r = th.cmd_scoring(_p(BAJO, remitente=AUTORA, prioritario=False), self._cfg())
        self.assertEqual(r["tier"], "READING_LATER")
        self.assertNotIn("suelo_aplicado", r)
        self.assertNotIn("aviso_prioritario", r)

    def test_coincidencias_anula_el_prioritario_y_su_mas_tres(self):
        out = th.cmd_coincidencias({"correos": [
            {"id": 1, "remitente": AUTORA, "asunto": "Ensayo"},
            {"id": 2, "remitente": "otra@x.example", "asunto": "Hola"}]}, self._cfg())
        r1, r2 = out["resultados"]
        self.assertTrue(r1["lectura"])
        self.assertFalse(r1["prioritario"])
        self.assertEqual(r1["extra_points_filtros"], 0)
        self.assertEqual([d.get("anulado_por") for d in r1["detalle"]
                          if d["filtro"] == "remitentes_prioritarios"],
                         ["remitentes_lectura"])
        self.assertFalse(r2["lectura"])

    def test_coincidencias_sin_la_lista_no_cambia(self):
        cfg = _sin_lista()
        cfg["filtros"]["remitentes_prioritarios"] = ["autora@boletin.example"]
        r = th.cmd_coincidencias({"correos": [{"id": 1, "remitente": AUTORA,
                                               "asunto": "x"}]}, cfg)["resultados"][0]
        self.assertNotIn("lectura", r)
        self.assertTrue(r["prioritario"])
        self.assertEqual(r["extra_points_filtros"], th.PUNTOS_PRIORITARIO)


class TestValidarConfig(unittest.TestCase):
    """D4 y D5: validar-config avisa, sin rechazar."""

    def _avisos(self, **filtros):
        c = copy.deepcopy(CFG)
        c["filtros"].update(filtros)
        return th._avisos_config_usuario(c)

    def test_sin_avisos_con_entradas_concretas(self):
        avisos, info = self._avisos(remitentes_lectura=[
            "autora@boletin.example", "@autora.substack.com"])
        self.assertFalse([a for a in avisos if "remitentes_lectura" in a], avisos)
        self.assertEqual(info["remitentes_lectura_efectivos"], 2)

    def test_dominio_compartido(self):
        avisos, _ = self._avisos(remitentes_lectura=["@substack.com", "gmail.com",
                                                     "@autora.substack.com"])
        aviso = [a for a in avisos if "compartidos" in a]
        self.assertEqual(len(aviso), 1, avisos)
        self.assertIn("2 dominio(s)", aviso[0])
        self.assertNotIn("autora.substack.com", aviso[0])

    def test_solape_con_prioritarios_y_con_ignorar(self):
        avisos, _ = self._avisos(
            remitentes_lectura=["autora@boletin.example", "@ensayos.example"],
            remitentes_prioritarios=["@boletin.example"],
            remitentes_ignorar=["spam@news.ensayos.example"])
        self.assertTrue(any("remitentes_prioritarios (autora@boletin.example)" in a
                            and "manda remitentes_lectura" in a for a in avisos), avisos)
        self.assertTrue(any("remitentes_ignorar (@ensayos.example)" in a
                            for a in avisos), avisos)

    def test_lista_mal_formada(self):
        avisos, info = self._avisos(remitentes_lectura="autora@boletin.example")
        self.assertTrue(any("filtros.remitentes_lectura debe ser una lista" in a
                            for a in avisos), avisos)
        self.assertEqual(info["remitentes_lectura_efectivos"], 0)
        avisos, _ = self._avisos(remitentes_lectura=["Autora Pérez", 3])
        self.assertTrue(any("no casarán nunca" in a for a in avisos), avisos)


class TestSolapan(unittest.TestCase):
    def test_casos(self):
        s = th._entradas_solapan
        self.assertTrue(s("a@x.example", "a+b@x.example"))
        self.assertTrue(s("a@sub.x.example", "@x.example"))
        self.assertTrue(s("@x.example", "a@x.example"))
        self.assertTrue(s("@sub.x.example", "x.example"))
        self.assertFalse(s("a@x.example", "b@x.example"))
        self.assertFalse(s("@nox.example", "@x.example"))
        self.assertFalse(s("Autora", "@x.example"))


class TestTotalidad(unittest.TestCase):
    """Gate #6: formas raras de la lista nunca rompen scoring ni coincidencias."""

    def test_formas_raras(self):
        for valor in (None, "autora@boletin.example", 3, {"a": 1}, [None, 3, []],
                      ["", "@", "@@", "autora@"]):
            cfg = copy.deepcopy(CFG)
            cfg["filtros"]["remitentes_lectura"] = valor
            r = th.cmd_scoring_dispatch(_p(ALTO, remitente=AUTORA), cfg)
            self.assertEqual(r["tier"], "REVIEW", valor)
            c = th.cmd_coincidencias({"correos": [{"remitente": AUTORA}]}, cfg)
            self.assertTrue(c["ok"], valor)
            th._avisos_config_usuario(cfg)


class TestHibrido(unittest.TestCase):
    """La regla vive en scoring: en híbrido se aplica igual con el
    `remitente` del control del principal (sin claves nuevas en el contrato)."""

    def test_modelos_validar_aplica_la_lectura(self):
        import modelos
        from tests.test_modelos import lote
        p = lote()
        p["config"]["filtros"]["remitentes_lectura"] = ["autora@boletin.example"]
        p["esperados"][0]["control"].update(remitente=AUTORA, extra_points=1000)
        r = modelos.ejecutar("validar", p)["resultados"][0]
        self.assertEqual(r["resultado"]["tier"], "READING_LATER", r)
        self.assertIn("lectura_aplicada", r["resultado"])


if __name__ == "__main__":
    unittest.main()
