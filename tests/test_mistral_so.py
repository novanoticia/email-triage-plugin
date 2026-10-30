"""Mistral: esquema nativo una sola vez, rechazo y consumo sin red."""
import json
import unittest
from unittest.mock import patch
from tests import DIR_SCRIPTS
from tests.test_jev import lote
from tests.test_evaluadores import sobre
import clasificadores as nc
import evaluadores as ev
import esquema
import mistral_so as p


class TestMistralStructured(unittest.TestCase):
    def test_peticion_y_destino(self):
        entrada, cfg = lote()
        esq = esquema.generar(cfg)
        body = p.cuerpo(p.MODELO_POR_DEFECTO, ev.mensajes(cfg, entrada['perfil_minimo'], entrada['emails'][0]), esq)
        self.assertEqual(body['response_format']['type'], 'json_schema')
        self.assertEqual(body['response_format']['json_schema']['schema'], esq)
        self.assertEqual(json.dumps(body).count('"additionalProperties"'), json.dumps(esq).count('"additionalProperties"'))
        with patch.object(nc, 'solicitar', return_value={}) as t:
            p.solicitar(body, 'ficticia', 30)
        t.assert_called_once_with('https://api.mistral.ai/v1/chat/completions', body, 'ficticia', 30)

    def test_refusal_modelo_y_usage(self):
        _, cfg = lote()
        r = sobre('mistral', cfg)
        self.assertEqual(p.uso(r), (100, 200))
        self.assertEqual(p.modelo_efectivo(r, p.MODELO_POR_DEFECTO), p.MODELO_POR_DEFECTO)
        r['choices'][0]['message']['refusal'] = 'No puedo.'
        with self.assertRaisesRegex(nc.ErrorClasificador, 'proveedor_rehusa'):
            p.extraer(r)
        r['usage']['completion_tokens'] = float('nan')
        self.assertIsNone(p.uso(r))
        with self.assertRaisesRegex(nc.ErrorClasificador, 'modelo_inesperado'):
            p.modelo_efectivo({'model': 'mistral-small'}, p.MODELO_POR_DEFECTO)
