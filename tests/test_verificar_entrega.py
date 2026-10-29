"""Entrega verificada con el transcript del host (v3.22.9).

Prueba real 2026-10-26: el principal copió a mano los extractos en el prompt
de Haiku y alteró 4 de 41 (una errata, una palabra cambiada, una línea
duplicada, una frase añadida). La huella mira el lote que el principal
declara y el eco solo el principio y el final: ninguno lo vio. `validar`
con `transcript_especialista` busca cada extracto completo en lo que el
especialista recibió de verdad. Transcripts sintéticos en tempfiles.
"""
import copy
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

    def transcript(self, prompt, forma="texto", extra=(), respuesta=None):
        """JSONL como el de Claude Code: la primera entrada `user` es el prompt
        y el especialista contesta con `respuesta` (por defecto, la del lote)."""
        contenido = prompt if forma == "texto" else [{"type": "text", "text": prompt}]
        if respuesta is None:
            respuesta = json.dumps(self.p["respuesta"], ensure_ascii=False)
        lineas = [{"type": "user", "message": {"role": "user", "content": contenido}},
                  {"type": "assistant", "message": {"role": "assistant",
                   "content": [{"type": "text", "text": respuesta}]}},
                  *extra]
        ruta = os.path.join(self.dir, "agent.jsonl")
        with open(ruta, "w", encoding="utf-8") as fh:
            for d in lineas:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
        return ruta

    def validar(self, ruta):
        self.p["transcript_especialista"] = ruta
        return m.ejecutar("validar", self.p)

    def prompt(self, extracto, ident="1"):
        return ("Evalúa estas unidades.\nID %s\nAsunto: Comité\n"
                '<email-body-data id="%s">\n%s\n</email-body-data>\nFin.' % (ident, ident, extracto))

    def test_entrega_identica_cuenta(self):
        como_json = "Lote:\n" + json.dumps(self.p["lote"], ensure_ascii=False)
        for forma, prompt in (("texto", self.prompt(self.extracto)),
                              ("bloques", self.prompt(self.extracto)), ("texto", como_json)):
            with self.subTest(forma=forma, prompt=prompt[:12]):
                r = self.validar(self.transcript(prompt, forma))
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

    def test_json_con_saltos_escapados_cuenta(self):
        # Revisión Codex P2 (PR #126): reflujado y serializado como JSON, los
        # `\\n` escapados no son espacios hasta desescaparlos.
        reflujado = self.extracto.replace(". ", ".\n   \t")
        prompt = json.dumps({"unidades": [{"id": "1", "extracto": reflujado}]})
        r = self.validar(self.transcript(prompt))
        self.assertIn("resultado", r["resultados"][0], r["resultados"][0])

    def dos_unidades(self):
        otro = th.cmd_sanitizar(CUERPO.replace("jueves", "viernes"), max_chars=300)["texto"]
        segundo = copy.deepcopy(self.p["esperados"][0])
        segundo.update(id="2", huella_extracto=th.huella_extracto(otro))
        self.p["esperados"].append(segundo)
        fila = copy.deepcopy(self.p["respuesta"]["evaluaciones"][0])
        fila["id"] = "2"
        self.p["respuesta"]["evaluaciones"].append(fila)
        self.p["lote"]["unidades"].append({"id": "2", "extracto": otro})
        return otro

    def test_extractos_intercambiados_entre_unidades_no_cuentan(self):
        # Revisión Codex P2 (PR #126): ambos textos están, pero cada uno bajo
        # el id del otro; los veredictos irían al correo equivocado.
        otro = self.dos_unidades()
        for prompt in (self.prompt(otro, "1") + self.prompt(self.extracto, "2"),
                       json.dumps({"unidades": [{"id": "1", "extracto": otro},
                                                {"id": "2", "extracto": self.extracto}]})):
            with self.subTest(prompt=prompt[:15]):
                r = self.validar(self.transcript(prompt))
                self.assertEqual([f["motivo"] for f in r["resultados"]],
                                 ["entrega_distinta", "entrega_distinta"])

    def test_cada_extracto_bajo_su_id_cuenta(self):
        otro = self.dos_unidades()
        prompt = self.prompt(self.extracto, "1") + self.prompt(otro, "2")
        r = self.validar(self.transcript(prompt))
        self.assertTrue(all("resultado" in f for f in r["resultados"]), r["resultados"])

    def test_texto_libre_sin_estructura_no_cuenta(self):
        # Sin etiqueta ni JSON no hay forma de saber dónde acaba el extracto.
        for prompt in ("--- ID 1 ---\n" + self.extracto, "Evalúa esto:\n" + self.extracto):
            with self.subTest(prompt=prompt[:10]):
                r = self.validar(self.transcript(prompt))
                self.assertEqual(r["resultados"][0]["motivo"], "entrega_distinta")

    def test_id_1_no_es_id_10(self):
        r = self.validar(self.transcript(self.prompt(self.extracto, "10")))
        self.assertEqual(r["resultados"][0]["motivo"], "entrega_distinta")

    def test_anadido_antes_o_despues_no_cuenta(self):
        # Revisión Codex P2 (PR #126): el extracto más « Urgente.» contenía
        # el original como subcadena y pasaba.
        for alterado in (self.extracto + " Urgente.", "Urgente. " + self.extracto):
            for prompt in (self.prompt(alterado),
                           json.dumps({"unidades": [{"id": "1", "extracto": alterado}]})):
                with self.subTest(prompt=prompt[:12], alterado=alterado[:8]):
                    r = self.validar(self.transcript(prompt))
                    self.assertEqual(r["resultados"][0]["motivo"], "entrega_distinta")

    def test_mismo_id_con_otro_texto_en_otra_parte_no_cuenta(self):
        prompt = self.prompt(self.extracto) + self.prompt(self.extracto + " Urgente.")
        r = self.validar(self.transcript(prompt))
        self.assertEqual(r["resultados"][0]["motivo"], "entrega_distinta")

    def test_pares_sustitutos_en_json_ascii_cuentan(self):
        # Revisión Codex P2 (PR #126): `ensure_ascii=True` escribe 📊 como
        # dos escapes; desescaparlos por separado no daba el carácter.
        extracto = th.cmd_sanitizar("Resumen 📊 trimestral. " + CUERPO, max_chars=300)["texto"]
        self.assertIn("📊", extracto)
        self.p["esperados"][0]["huella_extracto"] = th.huella_extracto(extracto)
        self.p["lote"]["unidades"][0]["extracto"] = extracto
        prompt = json.dumps(self.p["lote"], ensure_ascii=True)
        self.assertIn("\\ud83d", prompt)
        r = self.validar(self.transcript(prompt))
        self.assertIn("resultado", r["resultados"][0], r["resultados"][0])

    def test_json_de_ejemplo_dentro_del_correo_no_es_una_entrega(self):
        # Revisión Codex P2 (PR #126): un correo técnico con un ejemplo
        # `{"id": "1", "extracto": …}` contaba como segunda entrega de la unidad.
        cuerpo = 'Ejemplo de la API: {"id": "1", "extracto": "Ejemplo de la documentación"}. ' + CUERPO
        extracto = th.cmd_sanitizar(cuerpo, max_chars=300)["texto"]
        self.assertIn('"extracto"', extracto)
        self.p["esperados"][0]["huella_extracto"] = th.huella_extracto(extracto)
        self.p["lote"]["unidades"][0]["extracto"] = extracto
        r = self.validar(self.transcript(self.prompt(extracto)))
        self.assertIn("resultado", r["resultados"][0], r["resultados"][0])

    def test_id_de_otra_unidad_en_el_asunto_no_estorba(self):
        # Revisión Codex P2 (PR #126): «Asunto: … solicitud ID 2» entre la
        # cabecera y el extracto de la unidad 1 se tomaba por marca de unidad.
        otro = self.dos_unidades()
        prompt = json.dumps({"unidades": [
            {"id": "1", "asunto": "Seguimiento de la solicitud ID 2", "extracto": self.extracto},
            {"id": "2", "asunto": "Comité", "extracto": otro}]}, ensure_ascii=False)
        r = self.validar(self.transcript(prompt))
        self.assertTrue(all("resultado" in f for f in r["resultados"]), r["resultados"])

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
        # El texto de un `tool_result` (aquí, el de la entrega permitida) no es
        # lo que el especialista recibió del principal.
        self.p.update(acciones_especialista=1, herramientas_especialista=["SubagentHandback"])
        ruta = self.transcript("Evalúa la unidad 1.", extra=[
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "h1", "name": "SubagentHandback"}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "h1",
                 "content": '<email-body-data id="1">%s</email-body-data>' % self.extracto}]}}])
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

    # --- v3.22.10: herramientas leídas del transcript, no copiadas ---

    def con_herramientas(self, *nombres, repetir_id=False):
        bloques = [{"type": "tool_use", "id": "toolu_%d" % (0 if repetir_id else i),
                    "name": n, "input": {}} for i, n in enumerate(nombres)]
        # Claude Code guarda cada bloque en su propia entrada `assistant`.
        extra = [{"type": "assistant", "message": {"role": "assistant", "content": [b]}}
                 for b in bloques]
        return self.transcript(self.prompt(self.extracto), extra=extra)

    def test_herramienta_en_transcript_frena_aunque_se_declaren_cero(self):
        # Prueba real (v3.22.7): el principal declaró lo que convenía; ahora
        # el transcript manda.
        for nombres in (["Bash"], ["Read", "Grep"], ["mcp__gmail__search"],
                        ["SubagentHandback", "Read"], ["SubagentHandback", "SubagentHandback"]):
            with self.subTest(nombres=nombres):
                r = self.validar(self.con_herramientas(*nombres))
                self.assertFalse(r["ok"])
                self.assertEqual(r["motivo"], "especialista_uso_herramientas")
                self.assertTrue(r["usar_principal"])

    def test_server_tool_use_y_sin_nombre_tambien_cuentan(self):
        bloques = [{"type": "server_tool_use", "id": "s1", "name": "web_search"},
                   {"type": "tool_use", "id": "t1"}]
        for b in bloques:
            with self.subTest(tipo=b["type"]):
                ruta = self.transcript(self.prompt(self.extracto), extra=[
                    {"type": "assistant", "message": {"role": "assistant", "content": [b]}}])
                self.assertEqual(self.validar(ruta)["motivo"], "especialista_uso_herramientas")

    def test_solo_la_entrega_cuenta_si_se_declara(self):
        self.p.update(acciones_especialista=1, herramientas_especialista=["SubagentHandback"])
        r = self.validar(self.con_herramientas("SubagentHandback"))
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["herramientas_en_transcript"], ["SubagentHandback"])
        self.assertTrue(r["herramientas_verificadas"])

    def test_declarar_menos_acciones_que_el_transcript_no_cuenta(self):
        r = self.validar(self.con_herramientas("SubagentHandback"))  # declaradas: 0
        self.assertEqual(r["motivo"], "acciones_no_coinciden")
        self.assertTrue(r["usar_principal"])

    def test_mismo_id_repetido_cuenta_una_vez(self):
        self.p.update(acciones_especialista=1, herramientas_especialista=["SubagentHandback"])
        r = self.validar(self.con_herramientas("SubagentHandback", "SubagentHandback",
                                               repetir_id=True))
        self.assertTrue(r["ok"], r)

    def test_transcript_verifica_si_el_host_no_informa(self):
        self.p["acciones_especialista"] = "no_informado"
        r = self.validar(self.transcript(self.prompt(self.extracto)))
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["herramientas_verificadas"])
        self.assertEqual(r["herramientas_en_transcript"], [])
        r = self.validar(self.con_herramientas("Read"))
        self.assertEqual(r["motivo"], "especialista_uso_herramientas")

    def test_tool_use_en_entrada_user_tambien_cuenta(self):
        # Revisión Mistral (PR #127): fail-closed, venga en la entrada que venga.
        ruta = self.transcript(self.prompt(self.extracto), extra=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_use", "id": "x", "name": "Bash"}]}}])
        self.assertEqual(self.validar(ruta)["motivo"], "especialista_uso_herramientas")

    def test_tool_result_sin_su_tool_use_cuenta(self):
        # Si se perdió la llamada, el resultado prueba que corrió una herramienta.
        ruta = self.transcript(self.prompt(self.extracto), extra=[
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "perdido", "content": "salida"}]}}])
        r = self.validar(ruta)
        self.assertEqual(r["motivo"], "especialista_uso_herramientas")

    def test_tool_result_de_la_entrega_no_cuenta_dos_veces(self):
        self.p.update(acciones_especialista=1, herramientas_especialista=["SubagentHandback"])
        ruta = self.transcript(self.prompt(self.extracto), extra=[
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "h1", "name": "SubagentHandback"}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "h1", "content": "ok"}]}}])
        r = self.validar(ruta)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["herramientas_en_transcript"], ["SubagentHandback"])

    def test_sin_transcript_se_comporta_como_antes(self):
        r = m.ejecutar("validar", self.p)
        self.assertTrue(r["ok"])
        self.assertFalse(r["entrega_verificada"])
        self.assertNotIn("herramientas_en_transcript", r)
        self.assertNotIn("respuesta_desde_transcript", r)
        self.assertIn("resultado", r["resultados"][0])


    # --- v3.22.24: la respuesta es la que escribió el especialista ---
    # Prueba real 2026-10-28: el especialista no entregó y el principal sacó
    # el JSON de su transcript con un script propio; `validar` miraba lo que
    # el especialista recibió, no lo que contestó.

    def retocada(self):
        r = copy.deepcopy(self.p["respuesta"])
        vs = r["evaluaciones"][0]["verdicts"]
        k = next(iter(vs))
        opciones = list(m._criterios(self.p["config"])[k][0])
        vs[k] = next(o for o in opciones if o != vs[k])
        return r

    def con_respuesta(self, *textos, extra=()):
        # Una entrada `assistant` por texto, en orden, tras la primera.
        mas = [{"type": "assistant", "message": {"role": "assistant",
                "content": [{"type": "text", "text": t}]}} for t in textos[1:]]
        return self.transcript(self.prompt(self.extracto), respuesta=textos[0],
                               extra=[*mas, *extra])

    def test_veredicto_retocado_por_el_principal_no_cuenta(self):
        ruta = self.transcript(self.prompt(self.extracto))  # emite el original
        self.p["respuesta"] = self.retocada()
        fila = self.validar(ruta)["resultados"][0]
        self.assertEqual(fila["motivo"], "respuesta_distinta")
        self.assertTrue(fila["usar_principal"])
        self.assertNotIn("resultado", fila)

    def test_sin_respuesta_la_toma_del_transcript(self):
        ruta = self.transcript(self.prompt(self.extracto))
        del self.p["respuesta"]
        r = self.validar(ruta)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["respuesta_desde_transcript"])
        self.assertIn("resultado", r["resultados"][0])

    def test_con_respuesta_copiada_tal_cual_cuenta(self):
        r = self.validar(self.transcript(self.prompt(self.extracto)))
        self.assertFalse(r["respuesta_desde_transcript"])
        self.assertIn("resultado", r["resultados"][0])

    def test_bloque_json_con_texto_alrededor_cuenta(self):
        texto = "Aquí va:\n```json\n%s\n```\nFin." % json.dumps(self.p["respuesta"], indent=2)
        del self.p["respuesta"]
        r = self.validar(self.con_respuesta(texto))
        self.assertIn("resultado", r["resultados"][0], r)

    def test_si_corrige_vale_la_ultima(self):
        primera = json.dumps(self.retocada())
        ultima = json.dumps(self.p["respuesta"])
        r = self.validar(self.con_respuesta(primera, "Corrijo:", ultima))
        self.assertIn("resultado", r["resultados"][0], r)
        self.p["respuesta"] = json.loads(primera)
        r = self.validar(self.con_respuesta(primera, ultima))
        self.assertEqual(r["resultados"][0]["motivo"], "respuesta_distinta")

    def test_sin_respuesta_emitida_no_hay_nada_que_validar(self):
        for textos in (("No puedo evaluar estas unidades.",),
                       ('{"evaluacion": []}',), ('{"evaluaciones": [], "nota": 1}',)):
            with self.subTest(textos=textos):
                r = self.validar(self.con_respuesta(*textos))
                self.assertFalse(r["ok"])
                self.assertEqual(r["motivo"], "respuesta_no_emitida")
                self.assertTrue(r["usar_principal"])

    def test_json_en_el_prompt_no_es_lo_que_contesto(self):
        prompt = self.prompt(self.extracto) + "\nFormato: " + json.dumps(self.p["respuesta"])
        r = self.validar(self.transcript(prompt, respuesta="Hecho."))
        self.assertEqual(r["motivo"], "respuesta_no_emitida")

    def test_entrega_por_subagent_handback_cuenta(self):
        self.p.update(acciones_especialista=1, herramientas_especialista=["SubagentHandback"])
        for entrada in ({"result": json.dumps(self.p["respuesta"])},
                        {"result": copy.deepcopy(self.p["respuesta"])}):
            with self.subTest(tipo=type(entrada["result"]).__name__):
                ruta = self.transcript(self.prompt(self.extracto), respuesta="Entrego.", extra=[
                    {"type": "assistant", "message": {"role": "assistant", "content": [
                        {"type": "tool_use", "id": "h1", "name": "SubagentHandback",
                         "input": entrada}]}}])
                r = self.validar(ruta)
                self.assertTrue(r["ok"], r)
                self.assertIn("resultado", r["resultados"][0])

    def test_entrada_de_otra_herramienta_no_es_respuesta(self):
        # Además frena por herramientas; nunca cuenta como lo que contestó.
        ruta = self.transcript(self.prompt(self.extracto), respuesta="Hecho.", extra=[
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "b1", "name": "Bash",
                 "input": {"command": json.dumps(self.p["respuesta"])}}]}}])
        self.assertEqual(self.validar(ruta)["motivo"], "respuesta_no_emitida")

    def test_id_numerico_emitido_cuenta(self):
        emitida = copy.deepcopy(self.p["respuesta"])
        emitida["evaluaciones"][0]["id"] = 1
        r = self.validar(self.con_respuesta(json.dumps(emitida)))
        self.assertIn("resultado", r["resultados"][0], r)
        # Revisión Codex P2 (PR #143): también sin copiar `respuesta`.
        del self.p["respuesta"]
        r = self.validar(self.con_respuesta(json.dumps(emitida)))
        self.assertTrue(r["ok"], r)
        self.assertIn("resultado", r["resultados"][0], r)

    def test_fila_duplicada_en_lo_emitido_no_cuenta(self):
        emitida = copy.deepcopy(self.p["respuesta"])
        emitida["evaluaciones"].append(self.retocada()["evaluaciones"][0])
        r = self.validar(self.con_respuesta(json.dumps(emitida)))
        self.assertEqual(r["resultados"][0]["motivo"], "respuesta_distinta")

    def test_solo_la_fila_retocada_no_cuenta(self):
        otro = self.dos_unidades()
        prompt = self.prompt(self.extracto, "1") + self.prompt(otro, "2")
        ruta = self.transcript(prompt)
        self.p["respuesta"]["evaluaciones"][0] = self.retocada()["evaluaciones"][0]
        r = self.validar(ruta)
        self.assertEqual([f["motivo"] for f in r["resultados"]][0], "respuesta_distinta")
        self.assertIn("resultado", r["resultados"][1])

if __name__ == "__main__":
    unittest.main()
