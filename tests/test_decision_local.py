"""Modelos de decisión locales de Ollama (`/v1/systemone`), sin red real.

Correos ficticios; transporte simulado y, en un test, un servidor en 127.0.0.1.
"""
import copy
import http.server
import json
import os
from pathlib import Path
import threading
import unittest
import urllib.request
from unittest.mock import Mock, patch

from tests import DIR_SCRIPTS
from tests.test_jev import lote, respuesta as respuesta_jev
import clasificadores as nc
import decision_local as d

ACTIVO = {"activo": True, "acepta_envio_datos": True}


def respuesta(body, *_):
    r = respuesta_jev(body)
    r["model"] = body["model"]
    return r


def respuesta_dudosa(body, *_):
    """Como en la sonda real: elige, pero con confianza baja en todo."""
    r = respuesta(body)
    for k, q in body["questions"].items():
        ops = sorted(q["criteria"])
        elegido = ops[-1]
        ps = {o: (0.6 if o == elegido else 0.4 / (len(ops) - 1)) for o in ops}
        n = len(ops)
        r["answers"][k] = {"type": "choice", "choice": elegido, "probabilities": ps,
                           "confidence": (0.6 - 1 / n) / (1 - 1 / n)}
    return r


class TestDecisionLocal(unittest.TestCase):
    def setUp(self):
        self.p, self.cfg = lote()

    def comparar(self, capa=None, transporte=respuesta):
        return d.comparar(copy.deepcopy(self.p), self.cfg,
                          ACTIVO if capa is None else capa, transporte)

    def test_plantilla_y_contrato(self):
        import yaml
        plantilla = yaml.safe_load((Path(DIR_SCRIPTS).parent / "config-decision-local.yaml").read_text())
        self.assertEqual(plantilla, d.DEFAULT)
        self.assertEqual(d.ENDPOINT, "http://127.0.0.1:11434/v1/systemone")
        self.assertEqual(d.MODELOS, ("d1:latest", "tev1:4b"))
        self.assertIsNone(d.PROVEEDOR.variable_clave)

    def test_sin_clave_compara_y_no_mueve(self):
        # Sin ninguna variable de clave en el entorno: el proveedor local no la pide.
        with patch.dict(os.environ, {}, clear=True):
            t = Mock(side_effect=respuesta)
            r = self.comparar(transporte=t)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["cobertura"]["propuestas_comparadas"], 1)
        body, key, timeout = t.call_args.args
        self.assertIsNone(key)
        self.assertEqual(set(body), {"model", "state", "questions"})
        self.assertEqual(body["model"], "d1:latest")
        for campo in ("control", "principal", "hard_rules", "huella"):
            self.assertNotIn(campo, json.dumps(body))
        self.assertFalse(r["permitir_movimientos"])
        self.assertEqual(r["consumo"]["coste_estimado_usd"], 0)

    def test_los_proveedores_con_clave_siguen_exigiendola(self):
        import jev
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            t = Mock()
            r = jev.comparar(copy.deepcopy(self.p), self.cfg, ACTIVO, t)
        t.assert_not_called()
        self.assertEqual(r["resultados"][0]["motivo"], "credencial_ausente_o_invalida")

    def test_solo_modelos_sondeados_y_mismo_modelo_efectivo(self):
        for modelo in ("tev1:4b", "d1:latest"):
            r = self.comparar(dict(ACTIVO, modelo=modelo))
            self.assertTrue(r["ok"], r)
        for modelo in ("d1", "qwen3.5:latest", "jev-latest", "../d1"):
            t = Mock()
            r = self.comparar(dict(ACTIVO, modelo=modelo), t)
            t.assert_not_called()
            self.assertEqual(r["motivo"], "modelo_no_verificado")
        otro = lambda body, *_: dict(respuesta(body), model="tev1:4b")
        r = self.comparar(transporte=otro)
        self.assertEqual(r["resultados"][0]["motivo"], "modelo_inesperado")

    def test_hibrido_con_confianza_baja_vuelve_al_principal(self):
        # Medición real (12 correos ficticios): ninguna fila pasó el freno.
        p, cfg = lote()
        e = p["emails"][0]
        e.pop("principal")
        e["contexto_suficiente"] = True
        r = d.evaluar(p, cfg, dict(ACTIVO, modo="hibrido"), respuesta_dudosa)
        f = r["resultados"][0]
        self.assertEqual(f["motivo"], "confianza_baja")
        self.assertTrue(f["usar_principal"])
        self.assertNotIn("propuesta", f)
        self.assertFalse(r["permitir_movimientos"])

    def test_transporte_solo_loopback_sin_clave_ni_proxy(self):
        with patch.object(nc.urllib.request, "build_opener") as construir:
            resp = construir.return_value.open.return_value.__enter__.return_value
            resp.status, resp.read.return_value = 200, b"{}"
            resp.geturl.return_value = d.ENDPOINT
            with patch.dict(os.environ, {"HTTP_PROXY": "http://proxy.invalid:3128"}):
                self.assertEqual(d.solicitar({}, "ignorada", 30), {})
        req = construir.return_value.open.call_args.args[0]
        self.assertEqual(req.full_url, d.ENDPOINT)
        self.assertIsNone(req.get_header("Authorization"))
        proxy = [m for m in construir.call_args.args if isinstance(m, urllib.request.ProxyHandler)]
        self.assertEqual(proxy[0].proxies, {})

    def test_extremo_a_extremo_con_servidor_local(self):
        recibido = {}

        class Manejador(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                recibido["auth"] = self.headers.get("Authorization")
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                datos = json.dumps(respuesta(body)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(datos)

        servidor = http.server.HTTPServer(("127.0.0.1", 0), Manejador)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        destino = nc.LOOPBACK + "%d/v1/systemone" % servidor.server_port
        with patch.object(d, "ENDPOINT", destino):
            r = self.comparar(transporte=None)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["cobertura"]["propuestas_comparadas"], 1)
        self.assertIsNone(recibido["auth"])


if __name__ == "__main__":
    unittest.main()
