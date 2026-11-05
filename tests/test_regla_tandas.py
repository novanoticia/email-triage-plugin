"""Regla común de tandas para las capas externas (v3.28.2).

Prueba real 2026-11-03: con el mismo tope de 50 llamadas por ejecución, la
sesión partió 89 correos de Decisions en dos tandas y se negó a hacerlo con
Gemini, citando «no repetir para eludirlo», que solo estaba escrito en
`references/evaluadores.md`. Decidía el ánimo del modelo, no una regla. Por
decisión del mantenedor la regla es una sola, en el bloque «Evaluadores
externos» del SKILL.md: tandas solo si la persona pide más correos que el
tope, con las filas que la anterior dejó en `limite_llamadas`, hasta 500
correos por sesión entre todas, sin reenviar ninguno. El mantenedor pidió
2000; quedan en 500 porque `informe` no acepta más unidades por sesión
(`_INFORME_MAX_UNIDADES`) y una sesión que no puede cerrar su informe no es un
triaje válido. Si ese tope sube, este test pide subir también el de la regla.

Es doctrina, no un freno del script: este test vigila que la regla no se
contradiga en otro documento y que los motivos que cita sigan existiendo en
el código (deriva doc<->código). Sin red.
"""
import os
import re
import unittest

from tests import DIR_SCRIPTS
import triage_helpers as th

SKILL_DIR = os.path.normpath(os.path.join(DIR_SCRIPTS, ".."))
RUTA_SKILL = os.path.join(SKILL_DIR, "SKILL.md")
REFERENCIAS = ("jev.md", "decisions.md", "openrouter.md", "decision-local.md",
               "evaluadores.md")


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def _regla():
    texto = _leer(RUTA_SKILL)
    m = re.search(r"\*\*Tandas \(v[\d.]+\).*?(?=\n<!-- i18n:fin -->)", texto, re.S)
    return m.group(0) if m else ""


class TestReglaTandas(unittest.TestCase):
    def test_la_regla_vive_en_el_bloque_de_evaluadores_externos(self):
        texto = _leer(RUTA_SKILL)
        bloque = texto[texto.index("**Evaluadores externos.**"):]
        bloque = bloque[:bloque.index("<!-- i18n:fin -->")]
        self.assertIn("**Tandas (", bloque)
        for ref in REFERENCIAS:
            self.assertIn("references/" + ref, bloque)

    def test_la_regla_dice_lo_que_decidio_el_mantenedor(self):
        regla = " ".join(_regla().split())
        self.assertTrue(regla, "falta la regla de tandas en el SKILL.md")
        for trozo in ("por ejecución", "pide más correos que ese tope",
                      "`limite_llamadas`", "correos por sesión entre todas",
                      "nunca reenvíes un correo ya enviado",
                      "`proveedor_detenido`", "Sin número, una sola"):
            self.assertIn(trozo, regla)

    def test_el_tope_de_la_regla_es_el_de_informe(self):
        # Doc<->código: más correos de los que `informe` acepta dejarían la
        # sesión sin informe (5.R), y sin él el triaje no se puede cerrar.
        regla = " ".join(_regla().split())
        m = re.search(r"hasta (\d+) correos por sesión", regla)
        self.assertIsNotNone(m, "la regla no cita su tope de correos")
        self.assertEqual(int(m.group(1)), th._INFORME_MAX_UNIDADES)

    def test_los_motivos_que_cita_existen_en_el_codigo(self):
        # Si el script renombra un motivo, la regla deja de poder aplicarse.
        for fichero in ("clasificadores.py", "evaluadores.py"):
            codigo = _leer(os.path.join(DIR_SCRIPTS, fichero))
            for motivo in ("limite_llamadas", "proveedor_detenido"):
                self.assertIn('"%s"' % motivo, codigo, (fichero, motivo))

    def test_ninguna_referencia_la_contradice(self):
        for ref in REFERENCIAS:
            texto = " ".join(_leer(os.path.join(SKILL_DIR, "references", ref)).split())
            self.assertNotIn("no repetir para eludirlo", texto, ref)

    def test_evaluadores_remite_a_la_regla_comun(self):
        texto = " ".join(_leer(os.path.join(SKILL_DIR, "references",
                                            "evaluadores.md")).split())
        self.assertIn("varias ejecuciones solo valen como tandas", texto)


if __name__ == "__main__":
    unittest.main()
