"""Adaptador Apple Foundation Models (`fm serve`, modelo `pcc`).

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
import apple_so as p
import clasificadores as nc
import esquema
import evaluadores as ev


class TestAppleSO(unittest.TestCase):
    def test_contrato_comprobado_en_un_mac(self):
        self.assertEqual(p.ENDPOINT, "http://127.0.0.1:8765/v1/chat/completions")
        self.assertIsNone(p.VARIABLE_CLAVE)
        self.assertEqual(p.MODELOS, ("pcc",))
        _, cfg = lote()
        body = p.cuerpo("pcc", [{"role": "user", "content": "x"}], esquema.generar(cfg))
        self.assertIs(body["stream"], False)  # por defecto `fm serve` responde en streaming
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertTrue(body["response_format"]["json_schema"]["strict"])

    def test_system_no_se_admite_porque_no_cabe(self):
        # 4.096 tokens de contexto: unos 4.090 de entrada + 1.400 de respuesta.
        self.assertEqual(ev.config({"proveedor": "apple"})["modelo"], "pcc")
        with self.assertRaisesRegex(nc.ErrorClasificador, "modelo_no_verificado"):
            ev.config({"proveedor": "apple", "modelo": "system"})

    def test_modelo_y_uso(self):
        r = {"model": "pcc", "usage": {"prompt_tokens": 4087, "completion_tokens": 1427}}
        self.assertEqual(p.modelo_efectivo(r, "pcc"), "pcc")
        self.assertEqual(p.uso(r), (4087, 1427))
        with self.assertRaisesRegex(nc.ErrorClasificador, "modelo_inesperado"):
            p.modelo_efectivo({"model": "system"}, "pcc")

    def _abrir(self):
        op = patch.object(nc.urllib.request, "build_opener")
        construir = op.start()
        self.addCleanup(op.stop)
        r = construir.return_value.open.return_value.__enter__.return_value
        r.status, r.read.return_value = 200, b"{}"
        r.geturl.return_value = p.ENDPOINT
        return construir, r

    def test_transporte_loopback_sin_clave_ni_proxy(self):
        construir, _ = self._abrir()
        with patch.dict(os.environ, {"HTTP_PROXY": "http://proxy.invalid:3128"}):
            self.assertEqual(p.solicitar({}, "ignorada", 30), {})
        req = construir.return_value.open.call_args.args[0]
        self.assertEqual(req.full_url, p.ENDPOINT)
        self.assertIsNone(req.get_header("Authorization"))
        self.assertNotIn("ignorada", json.dumps(dict(req.header_items())))
        manejadores = construir.call_args.args
        proxy = [m for m in manejadores if isinstance(m, urllib.request.ProxyHandler)]
        self.assertEqual(len(proxy), 1)
        self.assertEqual(proxy[0].proxies, {})  # ignora el proxy del entorno
        self.assertTrue(any(isinstance(m, nc._SinRedireccion) for m in manejadores))

    def test_sin_clave_solo_loopback_y_con_clave_nunca_loopback(self):
        self._abrir()
        with self.assertRaisesRegex(nc.ErrorClasificador, "destino_no_permitido"):
            nc.solicitar("https://api.example.invalid/v1/chat/completions", {}, None, 5)
        with self.assertRaisesRegex(nc.ErrorClasificador, "destino_no_permitido"):
            nc.solicitar(p.ENDPOINT, {}, "clave", 5)

    def test_errores_de_transporte_sin_contenido(self):
        for error, codigo in ((urllib.error.HTTPError(p.ENDPOINT, 500, "SECRETO", {}, None), "http_500"),
                              (OSError("SECRETO"), "fallo_red_o_timeout")):
            with self.subTest(codigo=codigo), \
                    patch.object(nc.urllib.request, "build_opener") as op:
                op.return_value.open.side_effect = error
                with self.assertRaisesRegex(nc.ErrorClasificador, "^" + codigo + "$"):
                    p.solicitar({}, None, 1)

    def test_extremo_a_extremo_con_servidor_local_y_proxy_en_el_entorno(self):
        recibido = {}

        class Manejador(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                recibido["auth"] = self.headers.get("Authorization")
                recibido["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                datos = json.dumps({"model": "pcc", "choices": []}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(datos)

        servidor = http.server.HTTPServer(("127.0.0.1", 0), Manejador)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        destino = nc.LOOPBACK + "%d/v1/chat/completions" % servidor.server_port
        with patch.dict(os.environ, {"http_proxy": "http://proxy.invalid:9",
                                     "HTTP_PROXY": "http://proxy.invalid:9", "no_proxy": ""}):
            r = nc.solicitar(destino, {"stream": False}, None, 5)
        self.assertEqual(r["model"], "pcc")
        self.assertIsNone(recibido["auth"])
        self.assertEqual(recibido["body"], {"stream": False})


if __name__ == "__main__":
    unittest.main()
