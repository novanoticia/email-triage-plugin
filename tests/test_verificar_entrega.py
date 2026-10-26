"""Entrega verificada con el transcript del host (v3.22.9).

Prueba real 2026-10-26: el principal copió a mano los extractos en el prompt
de Haiku y alteró 4 de 41 (una errata, una palabra cambiada, una línea
duplicada, una frase añadida). La huella mira el lote que el principal
declara y el eco solo el principio y el final: ninguno lo vio. `validar`
con `transcript_especialista` busca cada extracto completo en lo que el
especialista recibió de verdad. Transcripts sintéticos en tempfiles.
"""
import json
import os
import shutil
import tempfile
import unittest

from tests import DIR_SCRIPTS  # noqa: F401  (pone scripts en sys.path)
import modelos as m
import triage_helpers as th
from tests.test_modelos import lote

CUERPO = ("La reunión del comité se adelanta al jueves. Trae el informe "
          "revisado y las cifras del segundo trimestre. ") * 40


class TestVerificarEntrega(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.extracto = th.cmd_sanitizar(CUERPO, max_chars=300)["texto"]
        self.p = lote()
        self.p["esperados"][0]["huella_extracto"] = th.huella_extracto(self.extracto)
        self.p["lote"] = {"unidades": [{"id": "1", "extracto": self.extracto}]}

    def transcript(self, prompt, forma="texto", extra=()):
        """JSONL como el de Claude Code: la primera entrada `user` es el prompt."""
        contenido = prompt if forma == "texto" else [{"type": "text", "text": prompt}]
        lineas = [{"type": "user", "message": {"role": "user", "content": contenido}},
                  {"type": "assistant", "message": {"role": "assistant",
                   "content": [{"type": "text", "text": "{\"evaluaciones\": []}"}]}},
                  *extra]
        ruta = os.path.join(self.dir, "agent.jsonl")
        with open(ruta, "w", encoding="utf-8") as fh:
            for d in lineas:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
        return ruta

    def validar(self, ruta):
        self.p["transcript_especialista"] = ruta
        return m.ejecutar("validar", self.p)

    def prompt(self, extracto):
        return "Evalúa estas unidades.\n--- ID 1 ---\nAsunto: Comité\n" + extracto + "\nFin."

    def test_entrega_identica_cuenta(self):
        for forma in ("texto", "bloques"):
            with self.subTest(forma=forma):
                r = self.validar(self.transcript(self.prompt(self.extracto), forma))
                self.assertTrue(r["ok"], r)
                self.assertTrue(r["entrega_verificada"])
                self.assertIn("resultado", r["resultados"][0])

    def test_solo_espacios_distintos_cuenta(self):
        reflujado = self.extracto.replace(". ", ".\n   ")
        r = self.validar(self.transcript(self.prompt(reflujado)))
        self.assertIn("resultado", r["resultados"][0], r["resultados"][0])

    def test_sin_marca_truncado_cuenta(self):
        sin_marca = self.extracto.replace(" [truncado]", "")
        r = self.validar(self.transcript(self.prompt(sin_marca)))
        self.assertIn("resultado", r["resultados"][0])

    def test_escapado_en_json_cuenta(self):
        prompt = json.dumps({"unidades": [{"id": "1", "extracto": self.extracto}]})
        r = self.validar(self.transcript(prompt))
        self.assertIn("resultado", r["resultados"][0])

    def test_los_casos_reales_de_corrupcion_en_medio(self):
        palabras = self.extracto.split()
        medio = len(palabras) // 2
        casos = {
            "errata": palabras[:medio] + ["ppensar"] + palabras[medio + 1:],
            "palabra_cambiada": palabras[:medio] + ["article"] + palabras[medio + 1:],
            "frase_añadida": palabras[:medio] + "Y una frase que no estaba.".split()
                             + palabras[medio:],
            "linea_perdida": palabras[:medio - 5] + palabras[medio + 5:],
        }
        for nombre, alterado in casos.items():
            with self.subTest(caso=nombre):
                r = self.validar(self.transcript(self.prompt(" ".join(alterado))))
                fila = r["resultados"][0]
                self.assertEqual(fila["motivo"], "entrega_distinta")
                self.assertTrue(fila["usar_principal"])
                self.assertNotIn("resultado", fila)

    def test_lo_que_responde_el_especialista_no_cuenta_como_recibido(self):
        # Si el extracto solo aparece en la respuesta del especialista, no lo recibió.
        ruta = self.transcript("Evalúa la unidad 1.", extra=[
            {"type": "assistant", "message": {"role": "assistant",
             "content": [{"type": "text", "text": self.extracto}]}}])
        self.assertEqual(self.validar(ruta)["resultados"][0]["motivo"], "entrega_distinta")

    def test_resultados_de_herramientas_no_cuentan(self):
        ruta = self.transcript("Evalúa la unidad 1.", extra=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "content": self.extracto}]}}])
        self.assertEqual(self.validar(ruta)["resultados"][0]["motivo"], "entrega_distinta")

    def test_transcript_irreconocible_o_ausente_no_da_por_bueno(self):
        vacio = os.path.join(self.dir, "vacio.jsonl")
        with open(vacio, "w", encoding="utf-8") as fh:
            fh.write('{"type": "summary"}\nno es json\n')
        for ruta, motivo in ((vacio, "transcript_no_reconocido"),
                             (os.path.join(self.dir, "no_existe.jsonl"), "transcript_ilegible"),
                             (self.dir, "transcript_ilegible"),
                             ("", "transcript_invalido"), (3, "transcript_invalido")):
            with self.subTest(ruta=ruta):
                r = self.validar(ruta)
                self.assertFalse(r["ok"])
                self.assertEqual(r["motivo"], motivo)
                self.assertTrue(r["usar_principal"])

    def test_sin_lote_no_hay_con_que_comparar(self):
        del self.p["lote"]
        r = self.validar(self.transcript(self.prompt(self.extracto)))
        self.assertEqual(r["motivo"], "transcript_sin_lote")

    def test_sin_transcript_se_comporta_como_antes(self):
        r = m.ejecutar("validar", self.p)
        self.assertTrue(r["ok"])
        self.assertFalse(r["entrega_verificada"])
        self.assertIn("resultado", r["resultados"][0])


if __name__ == "__main__":
    unittest.main()
