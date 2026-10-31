"""Contrato HTTP de OpenAI: red simulada y credenciales ficticias."""
import json
import unittest
from unittest.mock import patch
import urllib.error
from tests import DIR_SCRIPTS
import clasificadores as nc
import openai_so as p
from tests.test_evaluadores import sobre
from tests.test_jev import lote


class TestOpenAIStructured(unittest.TestCase):
    def test_sobre_estricto_sin_estado_ni_herramientas(self):
        esquema = {'type': 'object'}
        body = p.cuerpo(p.MODELO_POR_DEFECTO, [], esquema)
        self.assertIs(body['response_format']['json_schema']['strict'], True)
        self.assertIs(body['response_format']['json_schema']['schema'], esquema)
        self.assertFalse(body['store'])
        self.assertNotIn('tools', body)
        with patch.object(nc, 'solicitar', return_value={}) as t:
            p.solicitar(body, 'ficticia', 30)
        t.assert_called_once_with(p.ENDPOINT, body, 'ficticia', 30)

    def test_transporte_acotado_y_errores_sin_contenido(self):
        with patch.object(nc.urllib.request, 'build_opener') as op:
            r = op.return_value.open.return_value.__enter__.return_value
            r.status = 200
            r.geturl.return_value = p.ENDPOINT
            r.read.return_value = b'{}'
            p.solicitar({}, 'ficticia', 2)
            req = op.return_value.open.call_args.args[0]
            self.assertEqual(req.get_header('Authorization'), 'Bearer ficticia')
            r.read.assert_called_once_with(nc.MAX_JSON + 1)
            r.read.return_value = b'x' * (nc.MAX_JSON + 1)
            with self.assertRaisesRegex(nc.ErrorClasificador, 'respuesta_excesiva'):
                p.solicitar({}, 'ficticia', 2)
            op.return_value.open.side_effect = urllib.error.HTTPError(p.ENDPOINT, 401, 'SECRETO', {}, None)
            with self.assertRaisesRegex(nc.ErrorClasificador, '^http_401$'):
                p.solicitar({}, 'ficticia', 2)

    def test_json_duplicado_nan_y_tool_calls_no_se_reparan(self):
        _, cfg = lote()
        for texto in ('{"x":1,"x":2}', '{"x":NaN}', '```json\n{}\n```'):
            r = sobre('openai', cfg)
            r['choices'][0]['message']['content'] = texto
            with self.assertRaises((nc.ErrorClasificador, ValueError)):
                p.extraer(r)
        r = sobre('openai', cfg)
        r['choices'][0]['message']['tool_calls'] = [{}]
        with self.assertRaisesRegex(nc.ErrorClasificador, 'respuesta_incompleta'):
            p.extraer(r)

    def test_usage_y_coste_no_confunden_cache_con_entrada_simple(self):
        _, cfg = lote()
        r = sobre('openai', cfg)
        self.assertEqual(p.uso(r), (100, 200))
        self.assertTrue(p.coste_conocido(r))
        r['usage']['prompt_tokens_details'] = {'cache_write_tokens': 80}
        self.assertFalse(p.coste_conocido(r))
        r['usage']['prompt_tokens'] = -1
        self.assertIsNone(p.uso(r))
        with self.assertRaisesRegex(nc.ErrorClasificador, 'modelo_inesperado'):
            p.modelo_efectivo({'model': p.MODELO_POR_DEFECTO + '-inventado'}, p.MODELO_POR_DEFECTO)


class TestModeloEfectivo(unittest.TestCase):
    def test_acepta_el_snapshot_fechado_y_nada_mas(self):
        import openai_so
        pedido = openai_so.MODELO_POR_DEFECTO
        for devuelto in (pedido, pedido + "-2026-10-01"):
            self.assertEqual(openai_so.modelo_efectivo({"model": devuelto}, pedido), devuelto)
        for devuelto in (pedido + "-mini", pedido + "-2026-10", "gpt-otro", None, 5,
                         pedido + "-2026-10-01-extra"):
            with self.subTest(devuelto=devuelto):
                with self.assertRaisesRegex(Exception, "modelo_inesperado"):
                    openai_so.modelo_efectivo({"model": devuelto}, pedido)
