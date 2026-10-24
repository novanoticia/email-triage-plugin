"""Eco de lo que el especialista recibió (v3.21.36).

Prueba real 2026-10-24 (modo comparar): el principal copió a mano los
extractos en la llamada a Haiku; en la unidad 40 se coló texto ajeno, la 41
llegó cortada y en la 50 faltó una línea. La huella de v3.21.30 compara el
lote que el principal declara, no lo que envió. Ahora `sanitizar` devuelve
`ancla_extracto` y el especialista un `eco`; si no coinciden, `eco_distinto`.
Sin red; datos sintéticos.
"""
import unittest

from tests import DIR_SCRIPTS  # noqa: F401  (pone scripts en sys.path)
import modelos as m
import triage_helpers as th
from tests.test_modelos import lote

CUERPO = ("La reunión del comité se adelanta al jueves. Trae el informe "
          "revisado y las cifras del segundo trimestre. ") * 40


class TestAncla(unittest.TestCase):
    def test_sanitizar_devuelve_el_ancla_de_su_texto(self):
        r = th.cmd_sanitizar(CUERPO, max_chars=300)
        self.assertEqual(r["ancla_extracto"], th.ancla_extracto(r["texto"]))
        self.assertEqual(r["ancla_extracto"]["inicio"],
                         "la reunión del comité se adelanta")
        # El ancla es literal: con la marca, si el extracto la lleva.
        self.assertTrue(r["ancla_extracto"]["fin"].endswith("[truncado]"))

    def test_eco_literal_del_texto_truncado_coincide(self):
        # Revisión Codex (PR #105): el especialista copia las seis últimas
        # palabras tal como le llegaron, «[truncado]» incluido.
        texto = th.cmd_sanitizar(CUERPO, max_chars=300)["texto"]
        w = texto.split()
        ancla = th.ancla_extracto(texto)
        literal = {"inicio": " ".join(w[:6]), "fin": " ".join(w[-6:])}
        self.assertTrue(th.eco_coincide(literal, ancla))
        sin_marca = {"inicio": " ".join(w[:6]), "fin": " ".join(w[-7:-1])}
        self.assertTrue(th.eco_coincide(sin_marca, ancla))
        corto = {"inicio": " ".join(w[:6]), "fin": " ".join(w[-3:])}
        self.assertFalse(th.eco_coincide(corto, ancla))

    def test_el_eco_tolera_lo_que_un_modelo_no_conserva(self):
        ancla = th.ancla_extracto("Hola mundo, ¿qué TAL estás hoy aquí?")
        eco = {"inicio": "hola mundo, ¿qué tal estás hoy",
               "fin": "Mundo, ¿Qué tal  estás hoy aquí?"}
        self.assertTrue(th.eco_coincide(eco, ancla))

    def test_formas_raras_no_coinciden(self):
        ancla = th.ancla_extracto(CUERPO)
        for eco in (None, "texto", {}, {"inicio": 1, "fin": 2},
                    {"inicio": ancla["inicio"]}):
            self.assertFalse(th.eco_coincide(eco, ancla), eco)
        self.assertFalse(th.eco_coincide(dict(ancla), "no es un ancla"))


class TestValidarEco(unittest.TestCase):
    def setUp(self):
        self.extracto = th.cmd_sanitizar(CUERPO, max_chars=300)["texto"]
        self.p = lote()
        self.p["esperados"][0]["ancla_extracto"] = \
            th.ancla_extracto(self.extracto)

    def _con_eco(self, recibido):
        fila = self.p["respuesta"]["evaluaciones"][0]
        if recibido is None:
            fila.pop("eco", None)
        else:
            # El eco literal que pide el contrato, no el de ancla_extracto.
            w = recibido.split()
            fila["eco"] = {"inicio": " ".join(w[:6]), "fin": " ".join(w[-6:])}
        return m.ejecutar("validar", self.p)["resultados"][0]

    def test_mismo_texto_cuenta(self):
        self.assertIn("resultado", self._con_eco(self.extracto))

    def test_el_caso_real_texto_ajeno_al_final(self):
        fila = self._con_eco(self.extracto + " Correo 41: Oferta especial "
                             "solo hoy para suscriptores premium.")
        self.assertEqual(fila["motivo"], "eco_distinto")
        self.assertTrue(fila["usar_principal"])
        self.assertNotIn("resultado", fila)

    def test_el_caso_real_texto_cortado(self):
        fila = self._con_eco(self.extracto[:120])
        self.assertEqual(fila["motivo"], "eco_distinto")

    def test_sin_eco_no_cuenta_si_hay_ancla(self):
        self.assertEqual(self._con_eco(None)["motivo"], "eco_distinto")

    def test_sin_ancla_el_eco_es_opcional(self):
        # Aditivo: una sesión sin `ancla_extracto` valida como antes.
        del self.p["esperados"][0]["ancla_extracto"]
        self.assertIn("resultado", self._con_eco(None))
        self.assertIn("resultado", self._con_eco("cualquier cosa"))

    def test_campos_de_mas_siguen_rechazandose(self):
        self.p["respuesta"]["evaluaciones"][0]["score"] = 3
        fila = m.ejecutar("validar", self.p)["resultados"][0]
        self.assertEqual(fila["motivo"], "campos_incorrectos")


if __name__ == "__main__":
    unittest.main()
