"""Adaptador Ollama local (`ollama serve`, modelo `qwen3.5:latest`).

Sin red externa: transporte simulado y, en un test, un servidor en 127.0.0.1.
"""
import http.server
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

from tests import DIR_SCRIPTS  # noqa: F401  (añade los scripts al path)
from tests.test_jev import lote
from tests import test_evaluadores as te
import clasificadores as nc
import esquema
import evaluadores as ev
import ollama_so as p


class TestOllamaSO(unittest.TestCase):
    def test_contrato_comprobado_en_un_mac(self):
        self.assertEqual(p.ENDPOINT, "http://127.0.0.1:11434/v1/chat/completions")
        self.assertIsNone(p.VARIABLE_CLAVE)
        self.assertEqual(p.MODELOS, ("qwen3.5:latest",))
        _, cfg = lote()
        body = p.cuerpo("qwen3.5:latest", [{"role": "user", "content": "x"}], esquema.generar(cfg))
        self.assertIs(body["stream"], False)
        self.assertEqual(body["reasoning_effort"], "none")
        # v3.26.2: tope de salida = margen del preflight (nunca más de lo comprobado).
        self.assertEqual(body["max_tokens"], p.MARGEN_SALIDA)
        self.assertGreaterEqual(p.MAX_SALIDA, p.SALIDA_MAXIMA_OBSERVADA)
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertTrue(body["response_format"]["json_schema"]["strict"])

    def test_respuesta_cortada_por_el_tope_solo_descarta_su_correo(self):
        # Con `max_tokens`, un correo que se enreda acaba `finish_reason:
        # length`; no es un fallo de transporte y el lote sigue.
        cortada = {"model": p.MODELO_POR_DEFECTO, "choices": [{"finish_reason": "length",
                   "message": {"role": "assistant", "content": '{"evaluaciones": ['}}],
                   "usage": {"prompt_tokens": 4144, "completion_tokens": p.MAX_SALIDA}}
        with self.assertRaisesRegex(nc.ErrorClasificador, "^respuesta_incompleta$"):
            p.extraer(cortada)
        self.assertFalse("respuesta_incompleta".startswith(ev.DETIENEN))

    def test_solo_modelos_sondeados(self):
        self.assertEqual(ev.config({"proveedor": "ollama"})["modelo"], "qwen3.5:latest")
        for modelo in ("qwen3.5", "llama3", "tev1:4b"):
            with self.subTest(modelo=modelo), \
                    self.assertRaisesRegex(nc.ErrorClasificador, "modelo_no_verificado"):
                ev.config({"proveedor": "ollama", "modelo": modelo})

    def test_timeout_hasta_600_solo_en_ollama(self):
        # qwen3.5 tardó 105-119 s por correo en un MacBook Pro de 16 GB.
        self.assertEqual(ev.config({"proveedor": "ollama", "timeout_segundos": 300})["timeout_segundos"], 300)
        self.assertEqual(ev.config({"proveedor": "ollama", "timeout_segundos": 600})["timeout_segundos"], 600)
        with self.assertRaisesRegex(nc.ErrorClasificador, "limites_invalidos"):
            ev.config({"proveedor": "ollama", "timeout_segundos": 601})
        for nombre in ("openai", "mistral", "gemini", "apple"):
            with self.subTest(proveedor=nombre), \
                    self.assertRaisesRegex(nc.ErrorClasificador, "limites_invalidos"):
                ev.config({"proveedor": nombre, "timeout_segundos": 61})

    def test_modelo_y_uso(self):
        r = {"model": "qwen3.5:latest", "usage": {"prompt_tokens": 4144, "completion_tokens": 1873}}
        self.assertEqual(p.modelo_efectivo(r, "qwen3.5:latest"), "qwen3.5:latest")
        self.assertEqual(p.uso(r), (4144, 1873))
        with self.assertRaisesRegex(nc.ErrorClasificador, "modelo_inesperado"):
            p.modelo_efectivo({"model": "llama3"}, "qwen3.5:latest")

    def test_transporte_loopback_sin_clave_ni_proxy(self):
        op = patch.object(nc.urllib.request, "build_opener")
        construir = op.start()
        self.addCleanup(op.stop)
        r = construir.return_value.open.return_value.__enter__.return_value
        r.status, r.read.return_value = 200, b"{}"
        r.geturl.return_value = p.ENDPOINT
        with patch.dict(os.environ, {"HTTP_PROXY": "http://proxy.invalid:3128"}):
            self.assertEqual(p.solicitar({}, "ignorada", 30), {})
        req = construir.return_value.open.call_args.args[0]
        self.assertEqual(req.full_url, p.ENDPOINT)
        self.assertIsNone(req.get_header("Authorization"))
        self.assertNotIn("ignorada", json.dumps(dict(req.header_items())))
        proxy = [m for m in construir.call_args.args if isinstance(m, urllib.request.ProxyHandler)]
        self.assertEqual(len(proxy), 1)
        self.assertEqual(proxy[0].proxies, {})

    def test_errores_de_transporte_sin_contenido(self):
        for error, codigo in ((urllib.error.HTTPError(p.ENDPOINT, 500, "SECRETO", {}, None), "http_500"),
                              (OSError("SECRETO"), "fallo_red_o_timeout")):
            with self.subTest(codigo=codigo), \
                    patch.object(nc.urllib.request, "build_opener") as op:
                op.return_value.open.side_effect = error
                with self.assertRaisesRegex(nc.ErrorClasificador, "^" + codigo + "$"):
                    p.solicitar({}, None, 1)

    def test_extremo_a_extremo_con_servidor_local(self):
        recibido = {}

        class Manejador(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                recibido["auth"] = self.headers.get("Authorization")
                recibido["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                datos = json.dumps({"model": "qwen3.5:latest", "choices": []}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(datos)

        servidor = http.server.HTTPServer(("127.0.0.1", 0), Manejador)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        destino = nc.LOOPBACK + "%d/v1/chat/completions" % servidor.server_port
        with patch.dict(os.environ, {"http_proxy": "http://proxy.invalid:9",
                                     "HTTP_PROXY": "http://proxy.invalid:9", "no_proxy": ""}):
            r = nc.solicitar(destino, {"stream": False}, None, 5)
        self.assertEqual(r["model"], "qwen3.5:latest")
        self.assertIsNone(recibido["auth"])



class TestPreflightOllama(unittest.TestCase):
    """v3.26.1: `GET /api/ps` antes del primer correo, con un servidor real
    en 127.0.0.1:0 que responde a la vez a `/api/ps` y al chat."""

    def servidor(self, ps=None, estado_ps=200, redirigir=False):
        visto = {"gets": 0, "posts": 0}

        class Manejador(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def responder(self, codigo, datos, cabeceras=()):
                datos = json.dumps(datos).encode()
                self.send_response(codigo)
                for k, v in cabeceras:
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)

            def do_GET(self):
                visto["gets"] += 1
                visto["ruta_get"] = self.path
                if redirigir:
                    return self.responder(302, {}, [("Location", "http://127.0.0.1:9/x")])
                self.responder(estado_ps, ps)

            def do_POST(self):
                visto["posts"] += 1
                self.rfile.read(int(self.headers["Content-Length"]))
                self.responder(200, te.sobre("ollama", lote()[1]))

        srv = http.server.HTTPServer(("127.0.0.1", 0), Manejador)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = nc.LOOPBACK + "%d" % srv.server_port
        for nombre, ruta in (("PS", "/api/ps"), ("ENDPOINT", "/v1/chat/completions")):
            parche = patch.object(p, nombre, base + ruta)
            parche.start()
            self.addCleanup(parche.stop)
        entorno = patch.dict(os.environ, {"http_proxy": "http://proxy.invalid:9",
                                          "HTTP_PROXY": "http://proxy.invalid:9", "no_proxy": ""})
        entorno.start()
        self.addCleanup(entorno.stop)
        return visto

    def procesar(self):
        lote_, cfg = lote()
        capa = dict(te.ACTIVO, proveedor="ollama", timeout_segundos=30)
        return ev.procesar(lote_, cfg, capa, None, "comparar")

    @staticmethod
    def ps(contexto, nombre="qwen3.5:latest"):
        fila = {"name": nombre, "model": nombre, "size_vram": 1}
        if contexto is not None:
            fila["context_length"] = contexto
        return {"models": [fila]}

    def test_contexto_suficiente_sigue(self):
        visto = self.servidor(self.ps(16384))
        r = self.procesar()
        self.assertEqual(visto["ruta_get"], "/api/ps")
        self.assertEqual(r["preflight"]["contexto_servidor"], 16384)
        self.assertLess(r["preflight"]["contexto_necesario"], 16384)
        self.assertGreater(visto["posts"], 0)
        self.assertEqual(r["llamadas"], visto["posts"])
        self.assertNotIn(r["resultados"][0]["motivo"], ("contexto_insuficiente", "fallo_red_o_timeout"))

    def test_contexto_insuficiente_no_envia_ningun_correo(self):
        visto = self.servidor(self.ps(4096))
        r = self.procesar()
        self.assertEqual(visto["posts"], 0)
        self.assertEqual(r["llamadas"], 0)
        self.assertEqual(r["preflight"]["contexto_servidor"], 4096)
        self.assertGreater(r["preflight"]["contexto_necesario"], 4096)
        self.assertTrue(r["resultados"])
        for fila in r["resultados"]:
            self.assertEqual(fila["motivo"], "contexto_insuficiente")
            self.assertNotIn("propuesta", fila)

    def test_ps_inaccesible_da_el_motivo_de_transporte(self):
        visto = self.servidor()
        parche = patch.object(p, "PS", nc.LOOPBACK + "9/api/ps")  # puerto cerrado
        parche.start()
        self.addCleanup(parche.stop)
        r = self.procesar()
        self.assertEqual(visto["posts"], 0)
        self.assertEqual({f["motivo"] for f in r["resultados"]}, {"fallo_red_o_timeout"})

    def test_ps_con_error_http_o_redireccion(self):
        for kw, motivo in (({"estado_ps": 500}, "http_500"),
                           ({"redirigir": True}, "redireccion_rechazada")):
            with self.subTest(motivo=motivo):
                visto = self.servidor(**kw)
                r = self.procesar()
                self.assertEqual(visto["posts"], 0)
                self.assertEqual({f["motivo"] for f in r["resultados"]}, {motivo})

    def test_modelo_no_cargado_o_sin_contexto_declarado(self):
        for ps, motivo in ((self.ps(16384, "llama3:latest"), "modelo_no_cargado"),
                           ({"models": []}, "modelo_no_cargado"),
                           (self.ps(None), "contexto_no_verificable"),
                           (self.ps("16384"), "contexto_no_verificable"),
                           ({"modelos": []}, "respuesta_ps_invalida")):
            with self.subTest(motivo=motivo, ps=ps):
                visto = self.servidor(ps)
                r = self.procesar()
                self.assertEqual(visto["posts"], 0)
                self.assertEqual({f["motivo"] for f in r["resultados"]}, {motivo})

    def test_contexto_necesario_calculado_con_la_sonda(self):
        # El correo de `sonda_ollama.py` midió 4.144 tokens de entrada: la
        # estimación queda por encima (nunca corta) y de 4.096 no pasa.
        import yaml
        cfg = yaml.safe_load(open(os.path.join(os.path.dirname(ev.__file__), os.pardir, "config.yaml"),
                                  encoding="utf-8"))
        perfil = "Coordino una asociación cultural ficticia."
        correo = {"id": "1", "asunto": "¿Podemos vernos el jueves?", "remitente": "lucia@example.invalid",
                  "cuerpo": "Necesito que decidamos antes del viernes si renovamos el convenio. ¿Te va el jueves?"}
        e = ev.preparar({"perfil_minimo": perfil, "emails": [correo]})["emails"][0]
        body = p.cuerpo(p.MODELO_POR_DEFECTO, ev.mensajes(cfg, perfil, e), ev.esquema_evaluador(cfg))
        necesario = p.contexto_necesario(body)
        self.assertGreaterEqual(necesario - p.MARGEN_SALIDA, 4144)
        self.assertGreater(necesario, 4096)
        self.assertLessEqual(necesario, 16384)

    def test_la_lectura_get_solo_va_a_loopback(self):
        for destino, clave in (("https://api.example.invalid/api/ps", None),
                               ("https://api.example.invalid/api/ps", "k"),
                               (nc.LOOPBACK + "11434/api/ps", "k")):
            with self.subTest(destino=destino, clave=clave), \
                    patch.object(nc.urllib.request, "build_opener") as op:
                with self.assertRaisesRegex(nc.ErrorClasificador, "^destino_no_permitido$"):
                    nc.solicitar(destino, None, clave, 1)
                op.assert_not_called()

    def test_sin_filas_que_enviar_no_consulta(self):
        llamado = Mock()
        with patch.object(p, "preflight", llamado):
            lote_, cfg = lote()
            capa = dict(te.ACTIVO, proveedor="ollama", max_llamadas=1)
            for e in lote_["emails"]:
                e["contexto_suficiente"] = False
                e.pop("principal", None)
            ev.procesar(lote_, cfg, dict(capa, modo="hibrido"), Mock(), "hibrido")
        llamado.assert_not_called()

    def test_solo_cuentan_las_peticiones_que_se_enviaran(self):
        # Revisión Codex (PR #163): un correo bloqueado o fuera de
        # `max_llamadas` nunca se envía; no puede frenar a los demás.
        visto = {}

        def pre(modelo, bodies, timeout):
            visto["n"] = len(bodies)
            return {}

        lote_, cfg = lote(3)
        for e in lote_["emails"]:
            e.pop("principal", None)
            e["contexto_suficiente"] = True
        lote_["emails"][0]["contexto_suficiente"] = False
        capa = dict(te.ACTIVO, proveedor="ollama", modo="hibrido", max_llamadas=1)
        with patch.object(p, "preflight", pre):
            ev.procesar(lote_, cfg, capa, Mock(return_value={}), "hibrido")
        self.assertEqual(visto["n"], 1)

    def test_otros_proveedores_no_declaran_preflight(self):
        for nombre in ("openai", "mistral", "gemini", "apple"):
            with self.subTest(proveedor=nombre):
                self.assertFalse(hasattr(ev.proveedor(nombre), "preflight"))


if __name__ == "__main__":
    unittest.main()
