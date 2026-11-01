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
from unittest.mock import patch

from tests import DIR_SCRIPTS  # noqa: F401  (añade los scripts al path)
from tests.test_jev import lote
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
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertTrue(body["response_format"]["json_schema"]["strict"])

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


if __name__ == "__main__":
    unittest.main()
