"""Lotes de la delegación nativa (v3.28.12, decisión del mantenedor).

Prueba real 2026-11-23: con `capa_modelos` activa, el modelo no lanzó
ningún lote y ofreció la comparación al final («Cada lote de 7 exige copiar
a mano unos 16.000 caracteres y harían falta 8 lotes. Si la quieres,
dímelo»). La regla «no pidas permiso para delegar» existía desde v3.21.29;
lo que faltaba era quitar la excusa del coste. La nueva regla, en el bloque
de delegación del PASO 4.B, exige el primer lote siempre y, con más de dos,
una pausa tras él para confirmar (como la regla de tandas de las capas
externas).

Es doctrina, no un freno del script: el especialista no tiene herramientas,
así que el principal copia cada lote y no hay script donde engancharla. Este
test vigila que la regla esté donde se aplica, que diga lo decidido y que
`modelos-nativos.md` remita a ella sin contradecirla. Sin red.
"""
import os
import re
import unittest

from tests import DIR_SCRIPTS

SKILL_DIR = os.path.normpath(os.path.join(DIR_SCRIPTS, ".."))
RUTA_SKILL = os.path.join(SKILL_DIR, "SKILL.md")
RUTA_NATIVOS = os.path.join(SKILL_DIR, "references", "modelos-nativos.md")


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def _regla():
    texto = _leer(RUTA_SKILL)
    m = re.search(r"\*\*Lotes de la delegación \(v[\d.]+\)\.\*\*.*?(?=\n\*\*|\n<!-- i18n:fin -->)",
                  texto, re.S)
    return texto, (" ".join(m.group(0).split()) if m else "")


class TestReglaLotesDelegacion(unittest.TestCase):
    def test_la_regla_vive_en_el_bloque_de_delegacion(self):
        texto, regla = _regla()
        self.assertTrue(regla, "falta la regla de lotes en el SKILL.md")
        pos = texto.index("**Lotes de la delegación (")
        inicio = texto.rfind("<!-- i18n:inicio -->", 0, pos)
        bloque = texto[inicio:texto.index("<!-- i18n:fin -->", pos)]
        self.assertIn("delegar es un paso del triaje", bloque)
        self.assertLess(texto.rfind("Sin delegación, sigue este paso.", 0, pos), pos)
        self.assertLess(pos, texto.index("El modelo evalúa cada correo contra"))

    def test_dice_lo_que_decidio_el_mantenedor(self):
        _, regla = _regla()
        for trozo in ("El primer lote se lanza siempre y sin preguntar",
                      "ese coste no es motivo para dejar la delegación pendiente",
                      "Cuenta los lotes con el `tamano_lote` del plan",
                      "redondeando hacia arriba",
                      "Si harán falta más de dos lotes, tras el primero",
                      "cuántas filas del primero fueron comparables",
                      "espera a que la persona confirme",
                      "Nunca superes el `max_llamadas` de la capa"):
            self.assertIn(trozo, regla)

    def test_modelos_nativos_remite_a_la_regla(self):
        nativos = " ".join(_leer(RUTA_NATIVOS).split())
        self.assertIn("no pidas permiso para delegar", nativos)
        self.assertIn("el primer lote va siempre", nativos)
        self.assertIn("«Lotes de la delegación» en el PASO 4.B", nativos)
        # Ninguna frase que vuelva a convertir la delegación en una oferta.
        for contraria in ("pregunta antes de delegar", "ofrece la delegación",
                          "pide confirmación antes del primer lote"):
            self.assertNotIn(contraria, nativos)


if __name__ == "__main__":
    unittest.main()
