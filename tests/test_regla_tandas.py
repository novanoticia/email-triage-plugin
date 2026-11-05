"""Regla común de tandas para las capas externas (v3.28.2).

Prueba real 2026-11-03: con el mismo tope de 50 llamadas por ejecución, la
sesión partió 89 correos de Decisions en dos tandas y se negó a hacerlo con
Gemini, citando «no repetir para eludirlo», que solo estaba escrito en
`references/evaluadores.md`. Decidía el ánimo del modelo, no una regla. Por
decisión del mantenedor la regla es una sola, en el bloque «Evaluadores
externos» del SKILL.md: tandas solo si la persona pide más correos que el
tope, con los que faltan (los que la anterior dejó en `limite_llamadas` y los
que no entraron en ella, que admite como mucho `MAX_LOTE`), hasta 2000
correos por sesión entre todas, sin reenviar ninguno, y con más de dos, una
pausa tras la primera para confirmar el gasto. v3.28.2 lo dejó en 500 porque
`informe` no aceptaba más; v3.28.3 sube ese tope y el de las huellas
(`MAX_FILAS_HUELLAS`) a 2000. Una sesión que no puede cerrar su informe, o
cuyo freno de plantillas no mide, no es un triaje válido: este test ata los
tres números.

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
        for trozo in ("por ejecución", "pide más de los que caben en una",
                      "`limite_llamadas`", "los que no entraron en ella",
                      "correos por sesión entre todas",
                      "Nunca reenvíes un correo ya enviado",
                      "`proveedor_detenido`", "Sin número, una sola",
                      "Si van a ser más de dos, tras la primera",
                      "espera a que la persona confirme"):
            self.assertIn(trozo, regla)

    def test_el_tope_por_ejecucion_es_el_de_clasificadores(self):
        # Revisión Codex (PR #197): con 100 pedidos y `max_llamadas: 50`, la
        # primera ejecución no deja ninguno en `limite_llamadas`, porque solo
        # admite MAX_LOTE correos (`_filas`, también en evaluadores.py). La
        # regla tiene que contar también los que no entraron.
        import clasificadores
        regla = " ".join(_regla().split())
        m = re.search(r"cada ejecución admite como mucho (\d+) correos", regla)
        self.assertIsNotNone(m, "la regla no cita el tope de entrada")
        self.assertEqual(int(m.group(1)), clasificadores.MAX_LOTE)
        codigo = _leer(os.path.join(DIR_SCRIPTS, "evaluadores.py"))
        self.assertIn("nc._filas(p)", codigo)

    def test_el_tope_de_la_regla_es_el_de_informe(self):
        # Doc<->código: más correos de los que `informe` acepta dejarían la
        # sesión sin informe (5.R), y sin él el triaje no se puede cerrar.
        regla = " ".join(_regla().split())
        m = re.search(r"hasta (\d+) correos por sesión", regla)
        self.assertIsNotNone(m, "la regla no cita su tope de correos")
        self.assertEqual(int(m.group(1)), th._INFORME_MAX_UNIDADES)
        # v3.28.3: por encima de MAX_FILAS_HUELLAS el freno de plantillas
        # deja de medir (`lote_grande`); no puede quedar por debajo.
        self.assertGreaterEqual(th.MAX_FILAS_HUELLAS, th._INFORME_MAX_UNIDADES)

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
