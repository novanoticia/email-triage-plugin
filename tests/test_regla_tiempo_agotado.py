"""Regla de espera tras `tiempo_agotado` del lector de Mail.app (v3.28.17).

Prueba real 2026-11-25: una lectura de 100 correos agotó los 180 s del
lector y la de 50 lanzada al momento tardó 161 s, porque cortar `osascript`
no cancela la petición y Mail seguía atendiéndola. Medido el 2026-11-26 sin
solapamiento: 100 correos en unos 9 s, con picos de hasta 81 s. Por decisión
del mantenedor no se toca el tiempo límite: la regla es doctrina en el PASO 1
del SKILL.md (esperar al menos 2 minutos, repetir una sola vez, detener la
captura si vuelve a agotarse).

Es doctrina, no un freno del script: este test vigila que la regla siga en
su sitio, que la doctrina de reintentos remita a ella y que el código de
error que cita siga existiendo en el lector (deriva doc<->código). Sin red.
"""
import os
import re
import unittest

from tests import DIR_SCRIPTS

SKILL_DIR = os.path.normpath(os.path.join(DIR_SCRIPTS, ".."))
RUTA_SKILL = os.path.join(SKILL_DIR, "SKILL.md")
RUTA_DOCTRINA = os.path.join(SKILL_DIR, "references",
                             "paso-1-doctrina-ejecucion.md")
RUTA_LECTOR = os.path.join(DIR_SCRIPTS, "leer_mailapp.py")


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def _paso_1():
    texto = _leer(RUTA_SKILL)
    inicio = texto.index("## PASO 1 — Conectar al proveedor de correo")
    fin = texto.index("## PASO 1.B", inicio)
    return texto[inicio:fin]


class TestReglaTiempoAgotado(unittest.TestCase):
    def test_la_regla_vive_en_el_paso_1(self):
        paso = " ".join(_paso_1().split())
        m = re.search(r"\*\*Si el lector devuelve `tiempo_agotado` \(v[\d.]+\)\.\*\*"
                      r".*?(?=\*\*|$)", paso)
        self.assertTrue(m, "falta la regla de tiempo_agotado en el PASO 1")
        regla = m.group(0)
        for trozo in ("No relances la lectura enseguida",
                      "no cancela la petición",
                      "al menos 2 minutos",
                      "una sola vez",
                      "díselo a la persona",
                      "detén la captura"):
            self.assertIn(trozo, regla)

    def test_la_doctrina_de_reintentos_remite_a_la_regla(self):
        doctrina = " ".join(_leer(RUTA_DOCTRINA).split())
        seccion = doctrina[doctrina.index("## Reintentos"):]
        self.assertIn("`tiempo_agotado`, aplica antes la espera del PASO 1",
                      seccion)

    def test_el_lector_sigue_devolviendo_ese_codigo(self):
        codigo = _leer(RUTA_LECTOR)
        self.assertIn('ErrorCaptura("tiempo_agotado")', codigo)
        self.assertIn("subprocess.TimeoutExpired", codigo)


if __name__ == "__main__":
    unittest.main()
