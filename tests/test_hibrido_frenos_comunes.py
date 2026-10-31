"""Frenos de `hibrido` comunes a todos los clasificadores (v3.24.3).

Jev, Decisions y OpenRouter (`clasificadores.procesar`) se alinean con los
evaluadores LLM (`evaluadores.procesar`), que eran más estrictos:

- una fila frenada como `plantilla` vuelve al principal sin `propuesta` ni
  `payload_scoring` y no cuenta en `propuestas_validadas`;
- un fallo inesperado a mitad de lote no deja propuestas de las filas ya
  procesadas en una salida `ok: false`.

Sin red: transporte simulado.
"""
import os
import unittest
from unittest.mock import patch

from tests.test_decisions import respuesta as respuesta_decisions
from tests.test_jev import ACTIVO, lote, respuesta as respuesta_jev
from tests.test_openrouter import respuesta as respuesta_openrouter
import decisions as d
import jev as j
import openrouter as o

PROVEEDORES = (("jev", j, respuesta_jev), ("decisions", d, respuesta_decisions),
               ("openrouter", o, respuesta_openrouter))


def _hibrido(n):
    p, cfg = lote(n)
    for e in p["emails"]:
        e.pop("principal", None)
        e["contexto_suficiente"] = True
    return p, cfg


class TestFrenosComunesHibrido(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"TYPESAFE_API_KEY": "clave-ficticia",
                                      "OPENAI_API_KEY": "clave-ficticia",
                                      "OPENROUTER_API_KEY": "clave-ficticia"})
        env.start()
        self.addCleanup(env.stop)

    def test_plantilla_vuelve_al_principal_sin_propuesta(self):
        # Cinco correos con veredictos idénticos: huella de plantilla.
        for nombre, mod, transporte in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                p, cfg = _hibrido(5)
                r = mod.evaluar(p, cfg, dict(ACTIVO, modo="hibrido"), transporte)
                self.assertTrue(r["ok"], r)
                self.assertIn("alerta_plantilla", r)
                filas = [f for f in r["resultados"] if f["motivo"] == "plantilla"]
                self.assertEqual(len(filas), 5)
                for f in filas:
                    self.assertTrue(f["usar_principal"])
                    self.assertNotIn("propuesta", f)
                    self.assertNotIn("payload_scoring", f)
                self.assertEqual(r["cobertura"]["propuestas_validadas"], 0)
                self.assertEqual(r["cobertura"]["pendientes_principal"], 5)
                self.assertEqual(r["sin_propuesta"], 5)
                self.assertTrue(r["usar_principal"])
                self.assertFalse(r["permitir_movimientos"])

    def test_fallo_a_mitad_de_lote_no_deja_propuestas(self):
        for nombre, mod, base in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                p, cfg = _hibrido(2)
                llamadas = []

                def transporte(body, *args):
                    llamadas.append(1)
                    if len(llamadas) == 2:
                        raise TypeError("fallo inesperado con datos privados")
                    return base(body, *args)
                r = mod.evaluar(p, cfg, dict(ACTIVO, modo="hibrido"), transporte)
                self.assertFalse(r["ok"])
                self.assertEqual(r["motivo"], "entrada_invalida")
                self.assertTrue(r["usar_principal"])
                self.assertTrue(r["requiere_simulacion"])
                self.assertFalse(r["permitir_movimientos"])
                self.assertEqual(len(r["resultados"]), 2)
                for f in r["resultados"]:
                    self.assertTrue(f["usar_principal"])
                    self.assertNotIn("propuesta", f)
                    self.assertNotIn("payload_scoring", f)
                self.assertNotIn("privados", str(r))

    def test_sin_plantilla_ni_fallos_sigue_igual(self):
        for nombre, mod, transporte in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                p, cfg = _hibrido(1)
                r = mod.evaluar(p, cfg, dict(ACTIVO, modo="hibrido"), transporte)
                fila = r["resultados"][0]
                self.assertIn("payload_scoring", fila)
                self.assertIn("propuesta", fila)
                self.assertEqual(r["cobertura"]["propuestas_validadas"], 1)
                self.assertEqual(r["sin_propuesta"], 0)


if __name__ == "__main__":
    unittest.main()
