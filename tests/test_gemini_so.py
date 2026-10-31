"""Gemini: subconjunto JSON Schema, pensamientos y transporte sin fugas."""
import json
import unittest
from unittest.mock import patch
import urllib.error
from tests import DIR_SCRIPTS
from tests.test_jev import lote
from tests.test_evaluadores import sobre
import clasificadores as nc
import esquema
import gemini_so as p


class TestGeminiStructured(unittest.TestCase):
    def test_subconjunto_soportado_recorrido_y_esquema_sin_transformar(self):
        _, cfg = lote()
        esq = esquema.generar(cfg)
        body = p.cuerpo(p.MODELO_POR_DEFECTO, [{'content': 'Sistema'}, {'content': 'Datos'}], esq)
        self.assertIs(body['generationConfig']['responseFormat']['text']['schema'], esq)
        permitidas = {'type', 'properties', 'required', 'additionalProperties', 'enum', 'items', 'description'}
        def recorrer(nodo):
            self.assertLessEqual(set(nodo), permitidas)
            self.assertIn(nodo['type'], ('object', 'array', 'string', 'boolean'))
            if 'properties' in nodo:
                self.assertEqual(set(nodo['required']), set(nodo['properties']))
                self.assertIs(nodo['additionalProperties'], False)
                for sub in nodo['properties'].values(): recorrer(sub)
            if 'items' in nodo: recorrer(nodo['items'])
        recorrer(body['generationConfig']['responseFormat']['text']['schema'])
        self.assertNotIn('tools', body)

    def test_no_evalua_pensamientos_y_los_cuenta_en_coste(self):
        _, cfg = lote()
        r = sobre('gemini', cfg)
        esperado = p.extraer(r)
        r['candidates'][0]['content']['parts'].insert(0, {'text': 'SECRETO', 'thought': True})
        self.assertEqual(p.extraer(r), esperado)
        self.assertEqual(p.uso(r), (100, 220))
        r['usageMetadata']['thoughtsTokenCount'] = True
        self.assertIsNone(p.uso(r))

    def test_bloqueo_vacio_y_herramientas(self):
        _, cfg = lote()
        for r in ({'promptFeedback': {'blockReason': 'SAFETY'}}, {'candidates': []}):
            with self.assertRaisesRegex(nc.ErrorClasificador, 'proveedor_rehusa'):
                p.extraer(r)
        r = sobre('gemini', cfg)
        r['candidates'][0]['content']['parts'] = [{'functionCall': {'name': 'mover'}}]
        with self.assertRaisesRegex(nc.ErrorClasificador, 'respuesta_proveedor_invalida'):
            p.extraer(r)

    def test_transporte_clave_en_cabecera_limites_y_sin_redirect(self):
        with patch.object(nc.urllib.request, 'build_opener') as op:
            r = op.return_value.open.return_value.__enter__.return_value
            r.status = 200
            r.geturl.return_value = p.ENDPOINT
            r.read.return_value = b'{}'
            p.solicitar({}, 'ficticia', 2)
            req = op.return_value.open.call_args.args[0]
            self.assertEqual(req.get_header('X-goog-api-key'), 'ficticia')
            self.assertNotIn('ficticia', req.full_url)
            self.assertIsNone(req.get_header('Authorization'))
            self.assertEqual(req.full_url, p.ENDPOINT)
            r.read.assert_called_once_with(nc.MAX_JSON + 1)
            r.geturl.return_value = 'https://evil.invalid'
            with self.assertRaisesRegex(nc.ErrorClasificador, 'respuesta_http_inesperada'):
                p.solicitar({}, 'ficticia', 2)
            r.geturl.return_value = p.ENDPOINT
            r.read.return_value = b'x' * (nc.MAX_JSON + 1)
            with self.assertRaisesRegex(nc.ErrorClasificador, 'respuesta_excesiva'):
                p.solicitar({}, 'ficticia', 2)
        with self.assertRaisesRegex(nc.ErrorClasificador, 'redireccion_rechazada'):
            nc._SinRedireccion().redirect_request(None, None, 302, '', {}, 'https://evil.invalid')

    def test_errores_http_red_json_no_exponen_valores(self):
        for error, codigo in ((urllib.error.HTTPError(p.ENDPOINT, 403, 'SECRETO', {}, None), 'http_403'),
                              (OSError('SECRETO'), 'fallo_red_o_timeout'),
                              (ValueError('SECRETO'), 'respuesta_json_invalida')):
            with patch.object(nc.urllib.request, 'build_opener') as op:
                op.return_value.open.side_effect = error
                with self.assertRaisesRegex(nc.ErrorClasificador, '^' + codigo + '$'):
                    p.solicitar({}, 'ficticia', 1)
