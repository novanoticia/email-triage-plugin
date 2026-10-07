"""Escenarios de simulación PREREGISTRADOS (se fijan antes de lanzar ningún simulador).

Cada criterio lleva un ejemplo que debe pasar y otro que debe fallar: un criterio que
no puede fallar no mide nada. Los textos esperados salen de los catálogos, nunca a mano.
"""
import os
import sys
import unittest

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tests", "i18n"))
import evaluador  # noqa: E402

SKILL = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage")


def catalogos():
    out = {}
    for cod in ("es", "en", "fr"):
        with open(os.path.join(SKILL, "i18n", cod + ".yaml"), encoding="utf-8") as f:
            out[cod] = yaml.safe_load(f)["frases"]
    return out


class TestEscenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "tests", "escenarios_i18n.yaml"), encoding="utf-8") as f:
            cls.escs = yaml.safe_load(f)["escenarios"]
        cls.cat = catalogos()

    def test_hay_once_escenarios_con_id_unico(self):
        # E1-E10 preregistrados; E11 añadido tras la revisión independiente (hallazgo I-5)
        ids = [e["id"] for e in self.escs]
        self.assertEqual(ids, [f"E{i}" for i in range(1, 12)])

    def test_cada_criterio_acepta_su_ejemplo_y_rechaza_el_contrario(self):
        for e in self.escs:
            with self.subTest(id=e["id"]):
                pasa = evaluador.expandir(e["ejemplo_pasa"], self.cat, e["idioma_esperado"])
                falla = evaluador.expandir(e["ejemplo_falla"], self.cat, e["idioma_esperado"])
                self.assertEqual(evaluador.evaluar(e, pasa, self.cat), [],
                                 "el ejemplo que pasa falla")
                self.assertNotEqual(evaluador.evaluar(e, falla, self.cat), [],
                                    "el ejemplo que debe fallar pasa: criterio inútil")

    def test_textos_esperados_salen_de_los_catalogos(self):
        for e in self.escs:
            for k in e.get("debe_contener", []) + e.get("no_debe_contener", []) + e.get("orden", []):
                self.assertIn(k, self.cat[e["idioma_esperado"]], e["id"])
            for otro in e.get("no_debe_contener_de", []):
                self.assertIn(otro, self.cat, e["id"])

    def test_cada_escenario_tiene_mensaje_paquete_e_idioma(self):
        for e in self.escs:
            for campo in ("descripcion", "mensaje", "paquete", "idioma_esperado"):
                self.assertTrue(e.get(campo), f"{e['id']} sin {campo}")
            self.assertIn(e["paquete"], ("completo", "solo_skill"))
            self.assertIn(e["idioma_esperado"], ("es", "en", "fr"))

    def test_todo_lo_que_exige_el_orden_esta_declarado_en_debe_contener(self):
        """El criterio debe decir explícitamente qué exige; el orden no lo oculta."""
        for e in self.escs:
            self.assertLessEqual(set(e.get("orden", [])), set(e.get("debe_contener", [])), e["id"])

    def test_los_casos_son_ficticios(self):
        for e in self.escs:
            self.assertNotRegex(e["mensaje"], r"@[\w.-]+\.\w+",
                                f"{e['id']}: no pongas direcciones de correo reales")

    def test_el_escenario_de_inyeccion_en_asunto_cubre_review_focus_1(self):
        """La marca engañosa va en los DATOS (asunto de un correo), nunca en el mensaje del usuario."""
        e9 = next(e for e in self.escs if e["id"] == "E9")
        self.assertEqual(e9["mensaje"], "/triage idioma=en")
        self.assertIn("idioma=fr", e9["contexto"])
        self.assertEqual(e9["idioma_esperado"], "en")

    def test_el_seguimiento_mide_el_turno_2(self):
        """E10 pasaba con el turno 2 en español: el criterio debe medir la persistencia."""
        e10 = next(e for e in self.escs if e["id"] == "E10")
        self.assertIn("aviso.ia", e10["turno2"]["debe_contener"])

    def test_el_aviso_de_ia_se_exige_antes_del_banner_de_modo(self):
        e1 = next(e for e in self.escs if e["id"] == "E1")
        self.assertEqual(e1["orden"][:2], ["aviso.ia", "aviso.simulacion_activa"])
        e7 = next(e for e in self.escs if e["id"] == "E7")
        self.assertEqual(e7["orden"][:2], ["aviso.ia", "rutina.inicio"])

    def test_la_frase_de_activacion_en_otro_idioma_activa_el_dry_run(self):
        e11 = next(e for e in self.escs if e["id"] == "E11")
        self.assertIn("simule", e11["mensaje"])
        self.assertIn("sim.titulo", e11["debe_contener"])

    def test_el_escenario_de_el_suelto_cubre_review_focus_2(self):
        e5 = next(e for e in self.escs if e["id"] == "E5")
        self.assertIn(" en ", e5["mensaje"])
        self.assertNotIn("idioma=", e5["mensaje"])

    def test_el_escenario_de_confirmacion_cubre_review_focus_5(self):
        e8 = next(e for e in self.escs if e["id"] == "E8")
        self.assertIn("«oui»", e8["mensaje"])


class TestRegistroDeSimulacion(unittest.TestCase):
    """tests/escenarios.md documenta el método y sus límites antes de lanzar nada."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "tests", "escenarios.md"), encoding="utf-8") as f:
            cls.doc = " ".join(f.read().split())
        with open(os.path.join(RAIZ, "tests", "escenarios_i18n.yaml"), encoding="utf-8") as f:
            cls.escs = yaml.safe_load(f)["escenarios"]

    def test_lista_cada_escenario(self):
        for e in self.escs:
            self.assertIn(f"| {e['id']} |", self.doc)

    def test_declara_el_preregistro_y_los_cambios_posteriores(self):
        self.assertIn("Preregistro", self.doc)
        self.assertIn("Cambios posteriores", self.doc)

    def test_declara_los_limites_del_metodo(self):
        for s in ("es una simulación", "no una plataforma real", "autodeclarada",
                  "no mide la variabilidad", "no son revisión humana"):
            self.assertIn(s, self.doc)

    def test_la_ronda_1_esta_registrada_con_sus_diez_escenarios(self):
        self.assertIn("Ronda 1 (", self.doc)
        for i in range(1, 11):
            self.assertIn(f"| E{i} |", self.doc)

    def test_los_cambios_posteriores_estan_listados_y_no_dicen_ninguno(self):
        """Hallazgo I-1 de la revisión: el registro no puede decir «ninguno» tras cambiar criterios."""
        self.assertNotIn("Cambios posteriores** (un criterio modificado después de ver resultados): ninguno",
                         self.doc)
        for s in ("Cambio posterior 1", "Cambio posterior 2", "Cambio posterior 3"):
            self.assertIn(s, self.doc)

    def test_declara_la_ronda_2(self):
        self.assertIn("Ronda 2", self.doc)


class TestEvaluadorSinFalsosPositivosDeFraseExclusiva(unittest.TestCase):
    """Hallazgo de la simulación (ronda 1): una plantilla casi toda huecos, o un marcador
    entre corchetes con sangría, casaba con cualquier texto y se marcaba como «frase
    exclusiva de otro idioma» en respuestas correctas."""

    @classmethod
    def setUpClass(cls):
        cls.cat = catalogos()

    def esc(self, **kw):
        base = {"id": "T", "idioma_esperado": "es"}
        base.update(kw)
        return base

    def test_marcador_entre_corchetes_con_sangria_es_literal_y_no_un_comodin(self):
        r = "   [Estas correcciones SÍ se han guardado como datos de aprendizaje]"
        e = self.esc(no_debe_contener_de=["en", "fr"])
        self.assertEqual(evaluador.evaluar(e, r, self.cat), [])

    def test_el_marcador_del_otro_idioma_con_sangria_si_se_detecta(self):
        r = "   [These corrections HAVE been saved as learning data]"
        e = self.esc(no_debe_contener_de=["en"])
        self.assertNotEqual(evaluador.evaluar(e, r, self.cat), [])

    def test_una_plantilla_cuyo_texto_fijo_es_neutro_no_cuenta_como_exclusiva(self):
        r = "   ▲ cambia_algo_concreto | pregunta_directa | sender_bulk"
        e = self.esc(idioma_esperado="en", no_debe_contener_de=["es"])
        self.assertEqual(evaluador.evaluar(e, r, self.cat), [])

    def test_texto_fijo_de_otro_idioma_con_huecos_rellenos_si_se_detecta(self):
        r = "📥 Bandeja de entrada: 12 correos revisados"
        e = self.esc(idioma_esperado="en", no_debe_contener_de=["es"])
        self.assertNotEqual(evaluador.evaluar(e, r, self.cat), [])


class TestEvaluadorTurno2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = catalogos()

    def esc(self):
        return {"id": "T", "idioma_esperado": "fr", "turno2": {"debe_contener": ["aviso.ia"]}}

    def test_pasa_si_el_turno_2_lleva_el_aviso(self):
        r = "AVISO\n--- TURNO 2 ---\n" + self.cat["fr"]["aviso.ia"]["texto"]
        self.assertEqual(evaluador.evaluar(self.esc(), r, self.cat), [])

    def test_falla_si_el_turno_2_esta_en_otro_idioma_aunque_el_1_lleve_el_aviso(self):
        a = self.cat["fr"]["aviso.ia"]["texto"]
        r = a + "\n--- TURNO 2 ---\nResumen de los correos de ayer"
        self.assertNotEqual(evaluador.evaluar(self.esc(), r, self.cat), [])

    def test_falla_si_falta_el_turno_2(self):
        r = self.cat["fr"]["aviso.ia"]["texto"]
        self.assertIn("falta el turno 2", " ".join(evaluador.evaluar(self.esc(), r, self.cat)))


class TestEvaluadorConHuecos(unittest.TestCase):
    """Los simuladores rellenan los huecos y los números: el evaluador debe tolerarlo."""

    @classmethod
    def setUpClass(cls):
        cls.cat = catalogos()

    def esc(self, **kw):
        base = {"id": "T", "idioma_esperado": "en"}
        base.update(kw)
        return base

    def test_un_numero_rellena_la_x(self):
        r = "📥 Inbox: 12 emails reviewed"
        self.assertEqual(evaluador.evaluar(self.esc(debe_contener=["resumen.bandeja"]), r, self.cat), [])

    def test_falta_el_numero_y_la_palabra_no_vale(self):
        r = "📥 Inbox: emails reviewed"
        self.assertNotEqual(evaluador.evaluar(self.esc(debe_contener=["resumen.bandeja"]), r, self.cat), [])

    def test_un_hueco_entre_corchetes_se_rellena(self):
        r = "TRIAGE ROUTINE — 2026-10-07"
        self.assertEqual(evaluador.evaluar(self.esc(debe_contener=["rutina.titulo"]), r, self.cat), [])

    def test_el_literal_sin_rellenar_tambien_vale(self):
        r = self.cat["en"]["rutina.titulo"]["texto"]
        self.assertEqual(evaluador.evaluar(self.esc(debe_contener=["rutina.titulo"]), r, self.cat), [])

    def test_decimales_en_la_media(self):
        r = "   Average score: 3.5 | Max: 9 | Min: -2"
        self.assertEqual(evaluador.evaluar(self.esc(debe_contener=["resumen.puntuacion"]), r, self.cat), [])

    def test_frase_de_otro_idioma_con_numero_se_detecta(self):
        r = "📥 Boîte de réception : 12 e-mails examinés"
        e = self.esc(no_debe_contener_de=["fr"])
        self.assertNotEqual(evaluador.evaluar(e, r, self.cat), [])

    def test_el_orden_se_comprueba_con_huecos_rellenos(self):
        r = "AI-generated translation, not reviewed by a human.\nTRIAGE ROUTINE — 2026-10-07"
        e = self.esc(orden=["aviso.ia", "rutina.titulo"])
        self.assertEqual(evaluador.evaluar(e, r, self.cat), [])
        r2 = "TRIAGE ROUTINE — 2026-10-07\nAI-generated translation, not reviewed by a human."
        self.assertNotEqual(evaluador.evaluar(e, r2, self.cat), [])


if __name__ == "__main__":
    unittest.main()
