"""Contrato de la interfaz de revisión (v3.15, auditoría 2026-10-08 F1–F6).

El SKILL.md ES la implementación de la interfaz: estas pruebas fijan regla a regla
lo que antes quedaba al criterio del agente (y que en la sesión real se improvisó).
"""
import os
import re
import unittest

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage")


def leer(*p):
    with open(os.path.join(SKILL, *p), encoding="utf-8") as f:
        return f.read()


def plano(t):
    return " ".join(t.split())


class TestStubEnSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = leer("SKILL.md")
        cls.k = plano(s[s.index("### 4.K"):s.index("### 4.J")])
        cls.skill = s

    def test_la_respuesta_segura_esta_siempre_en_contexto(self):  # F2
        for frase in ("Solo un sí explícito mueve correo.",
                      "Una respuesta vacía, sin opción elegida o ambigua **no mueve nada**",
                      "vuelve a preguntar una sola vez",
                      "El silencio nunca es aceptación."):
            self.assertIn(frase, self.k)

    def test_el_stub_manda_leer_la_referencia(self):
        self.assertIn("`references/interfaz-revision.md`", self.k)
        self.assertTrue(os.path.exists(os.path.join(SKILL, "references", "interfaz-revision.md")))

    def test_4g_declara_por_tier_por_defecto_y_el_umbral(self):  # F1
        g = plano(self.skill[self.skill.index("### 4.G"):self.skill.index("### 4.K")])
        self.assertIn("**Modo `por_tier`** (por defecto desde v3.15)", g)
        self.assertIn("`interaccion.umbral_uno_a_uno`", g)
        self.assertNotIn("**Modo `confirmacion`** (por defecto)", g)

    def test_resumen_sin_version_fija_con_informe_y_deshacer(self):  # F6
        r = self.skill[self.skill.index("### Resumen de sesión real"):]
        self.assertNotIn("RESUMEN DE TRIAJE v3.0", r)
        self.assertIn("📄 Informe: [ruta del informe]", r)
        self.assertIn("↩️ Para deshacer: «deshaz el triaje»", r)

    def test_el_informe_se_pasa_por_fichero_nunca_por_la_shell(self):
        s = self.skill[self.skill.index("## PASO 5.R"):self.skill.index("## PASO 5.B")]
        self.assertIn("**por fichero**", s)
        ref = leer("references", "paso-5r-informe.md")
        bash = re.search(r"```bash\n(.*?)\n```", ref, re.S).group(1)
        self.assertNotIn("echo", bash)
        self.assertNotIn("<<", bash)
        self.assertIn("informe < ~/.email-triage/tmp/informe.json", bash)


class TestReferenciaInterfaz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = leer("references", "interfaz-revision.md")
        cls.p = plano(cls.t)

    def test_progreso(self):  # F5
        for l in ("⏳ Leyendo [carpeta]…", "📥 [carpeta]: N correos", "⏳ Cuerpos: N/M"):
            self.assertIn(l, self.t)

    def test_numeracion_estable_ligada_al_message_id(self):  # F3
        self.assertIn("`#N → message-id(s)`", self.p)
        self.assertIn("Los números no se reasignan aunque cambie un tier", self.p)

    def test_formato_compacto_y_detalle_bajo_peticion(self):  # F4
        self.assertIn("| #N | [Asunto] · [Remitente] · [DD/MM] | X | ▲ [razón] · ▼ [razón] |", self.t)
        self.assertIn("`detalle #N`", self.p)

    def test_reading_later_no_se_pregunta(self):  # F1
        self.assertIn("`READING_LATER` no se pregunta porque no se mueve", self.p)

    def test_una_correccion_se_registra(self):
        self.assertIn("es una corrección: regístrala en `correcciones.jsonl`", self.p)


class TestConfigPlantilla(unittest.TestCase):
    def test_modo_por_defecto_por_tier_y_umbral(self):
        with open(os.path.join(SKILL, "config.yaml"), encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.assertEqual(cfg["interaccion"]["modo"], "por_tier")
        self.assertEqual(cfg["interaccion"]["umbral_uno_a_uno"], 8)


if __name__ == "__main__":
    unittest.main()
