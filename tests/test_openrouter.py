"""Contrato OpenRouter con correos ficticios, sin red ni crédito."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from tests import DIR_SCRIPTS
from tests.test_jev import lote, respuesta as respuesta_jev
import clasificadores as nc
import openrouter as o
import jev

ACTIVO = {"activo": True, "acepta_envio_datos": True}


def respuesta(body, *_):
    r = respuesta_jev(body)
    r["model"] = body["model"]
    return r


class TestOpenRouter(unittest.TestCase):
    def setUp(self):
        self.p, self.cfg = lote()
        env = patch.dict(os.environ, {"OPENROUTER_API_KEY": "clave-test-openrouter-987"})
        env.start()
        self.addCleanup(env.stop)

    def comparar(self, capa=None, transporte=respuesta):
        return o.comparar(copy.deepcopy(self.p), self.cfg,
                          ACTIVO if capa is None else capa, transporte)

    def test_plantilla_y_modelo_por_defecto(self):
        import yaml
        cfg = yaml.safe_load((Path(DIR_SCRIPTS).parent / 'config-openrouter.yaml').read_text())
        self.assertEqual(cfg, o.DEFAULT)
        self.assertEqual(cfg['modelo'], 'microsoft/microsoft-decision-1')

    def test_opt_in_y_clave_independientes(self):
        for capa in ({}, {'activo': True}, {'acepta_envio_datos': True}):
            t = Mock()
            r = self.comparar(capa, t)
            t.assert_not_called()
            self.assertTrue(r['usar_principal'])
            self.assertFalse(r['permitir_movimientos'])
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': '', 'OPENAI_API_KEY': 'otra',
                                     'TYPESAFE_API_KEY': 'otra'}):
            t = Mock()
            r = self.comparar(transporte=t)
            t.assert_not_called()
            self.assertEqual(r['resultados'][0]['motivo'], 'credencial_ausente_o_invalida')

    def test_cambiar_modelo_solo_cambia_modelo(self):
        for modelo in (o.MODELO_POR_DEFECTO, 'typesafe/jev-1.14',
                       'openai/gpt-6-luna-decisions', 'inception/mercury-decide:free'):
            t = Mock(side_effect=respuesta)
            r = self.comparar(dict(ACTIVO, modelo=modelo), t)
            self.assertTrue(r['ok'], r)
            self.assertEqual(r['cobertura']['propuestas_comparadas'], 1)
            body, key, timeout = t.call_args.args
            self.assertEqual(body['model'], modelo)
            self.assertEqual(set(body), {'model', 'state', 'questions'})
            self.assertEqual(set(body['state']), {'perfil_minimo', 'correo'})
            self.assertEqual(key, 'clave-test-openrouter-987')
            self.assertEqual(timeout, 15)
            for campo in ('control', 'principal', 'hard_rules', 'huella', 'clave-test-openrouter-987'):
                self.assertNotIn(campo, json.dumps(body))
            self.assertFalse(r['permitir_movimientos'])
            self.assertIsNone(r['consumo']['coste_estimado_usd'])
            self.assertTrue(r['consumo']['coste_total_desconocido'])

    def test_config_y_modelos_invalidos_no_envian(self):
        for cambio in ({'modelo': 'Microsoft-Decision-1'}, {'modelo': True},
                       {'modelo': 'https://evil.invalid/model'}, {'modelo': 'a/../b'},
                       {'modelo': 'openrouter/auto'}, {'endpoint': 'https://evil.invalid'},
                       {'max_llamadas': 51}, {'modo': 'hibrido'}):
            t = Mock()
            self.assertFalse(self.comparar(dict(ACTIVO, **cambio), t)['ok'])
            t.assert_not_called()

    def test_modelo_efectivo_y_snapshot(self):
        for efectivo, valido in ((o.MODELO_POR_DEFECTO, True),
                                 (o.MODELO_POR_DEFECTO + '-20261009', True),
                                 ('typesafe/jev-1.14', False),
                                 (o.MODELO_POR_DEFECTO + '-otro', False), (None, False)):
            def t(body, *_):
                return dict(respuesta(body), model=efectivo)
            fila = self.comparar(transporte=t)['resultados'][0]
            self.assertEqual('propuesta' in fila, valido)
            if not valido:
                self.assertEqual(fila['motivo'], 'modelo_inesperado')

    def test_equivalencia_con_jev(self):
        qs = o._preguntas(self.cfg, nc._opciones(self.cfg))
        self.assertEqual(qs, jev._preguntas(self.cfg, nc._opciones(self.cfg)))
        body = o._cuerpo(o.MODELO_POR_DEFECTO, {}, {}, qs)
        r = respuesta(body)
        esperado = jev.validar_respuesta(dict(r, model='jev-1.14.0'), qs, 'jev-latest')
        self.assertEqual(o.validar_respuesta(r, qs, body['model']), esperado)

    def test_respuestas_invalidas_abstienen(self):
        def falta(r): r['answers'].pop(next(iter(r['answers'])))
        def sobra(r): r['answers']['inventado'] = {}
        def rechazo(r): r['answers'][next(iter(r['answers']))] = {'type': 'refusal'}
        def prob(r): next(iter(r['answers'].values()))['probabilities'] = {'si': True}
        def confianza(r): next(iter(r['answers'].values()))['confidence'] = float('nan')
        def uso(r): r['usage'] = {}
        for mutar in (falta, sobra, rechazo, prob, confianza, uso):
            def t(body, *_):
                r = respuesta(body)
                mutar(r)
                return r
            fila = self.comparar(transporte=t)['resultados'][0]
            self.assertNotIn('propuesta', fila)
            self.assertTrue(fila['usar_principal'])

    def test_s0_y_lote_invalidos_sin_red(self):
        self.p['emails'][0]['control']['tier_maximo'] = 'REVIEW'
        t = Mock()
        self.assertEqual(self.comparar(transporte=t)['resultados'][0]['motivo'], 's0_o_cap')
        t.assert_not_called()
        self.p, self.cfg = lote(2)
        self.p['emails'][1]['huella'] = 'alterada'
        self.assertFalse(self.comparar(transporte=t)['ok'])
        t.assert_not_called()

    def test_limites_y_error_sin_reintentos(self):
        self.p, self.cfg = lote(3)
        t = Mock(side_effect=respuesta)
        r = self.comparar(dict(ACTIVO, max_llamadas=1), t)
        self.assertEqual(t.call_count, 1)
        self.assertEqual(r['resultados'][1]['motivo'], 'limite_llamadas')
        t = Mock(side_effect=o.ErrorOpenRouter('http_429'))
        r = self.comparar(transporte=t)
        self.assertEqual(t.call_count, 1)
        self.assertEqual(r['resultados'][1]['motivo'], 'proveedor_detenido')

    def test_hibrido_revisado_sin_movimientos(self):
        for e in self.p['emails']:
            e.pop('principal')
            e['contexto_suficiente'] = True
        r = o.evaluar(self.p, self.cfg, dict(ACTIVO, modo='hibrido'), respuesta)
        self.assertTrue(r['ok'], r)
        self.assertIn('payload_scoring', r['resultados'][0])
        self.assertTrue(r['resultados'][0]['revision_obligatoria'])
        self.assertFalse(r['permitir_movimientos'])

    def test_transporte_destino_fijo(self):
        with patch.object(nc, 'solicitar', return_value={}) as t:
            o.solicitar({'model': o.MODELO_POR_DEFECTO}, 'clave-test-openrouter-987', 15)
        self.assertEqual(t.call_args.args[0], 'https://openrouter.ai/api/alpha/decisions')

    def test_cli_desactivado_y_config_no_canonico(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, EMAIL_TRIAGE_HOME=tmp)
            script = str(Path(DIR_SCRIPTS) / 'openrouter.py')
            r = subprocess.run([sys.executable, script, 'comparar', '--config', '/no-existe'],
                               input='{}', text=True, capture_output=True, env=env)
            self.assertEqual(json.loads(r.stdout)['motivo'], 'desactivado')
            self.assertEqual(r.returncode, 0)
            capa = Path(tmp) / 'config-openrouter.yaml'
            capa.write_text('activo: true\nacepta_envio_datos: true\n')
            otra = Path(tmp) / 'otra.yaml'
            otra.write_text('activo: true\nacepta_envio_datos: true\nmodelo: typesafe/jev-1.14\n')
            r = subprocess.run([sys.executable, script, 'comparar', '--config', '/no-existe',
                                '--config-openrouter', str(otra)], input='{}', text=True,
                               capture_output=True, env=env)
            self.assertEqual(json.loads(r.stdout)['motivo'], 'config_no_coincide_con_base')

    def test_modelo_vacio_no_envia_y_omision_usa_default(self):
        t = Mock()
        r = self.comparar(dict(ACTIVO, modelo=''), t)
        t.assert_not_called()
        self.assertEqual(r['diagnostico_error'], 'identificador_modelo_invalido')
        self.assertEqual(o._config(ACTIVO)['modelo'], o.MODELO_POR_DEFECTO)

    def test_config_personalizada_leida_sin_alterar_otras_capas(self):
        import tempfile
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            otros = {nombre: base / nombre for nombre in
                     ('config-jev.yaml', 'config-decisions.yaml')}
            for ruta in otros.values():
                ruta.write_text('activo: true\nmodelo: personalizado\n')
            antes = {nombre: ruta.read_bytes() for nombre, ruta in otros.items()}
            ruta = base / 'config-openrouter.yaml'
            capa = dict(ACTIVO, modelo='typesafe/jev-1.14', confianza_minima=0.9)
            ruta.write_text(yaml.safe_dump(capa))
            original = ruta.read_bytes()
            cargada = nc.capa_desde_disco(str(ruta), str(ruta), o._yaml, o._config)
            t = Mock(side_effect=respuesta)
            self.comparar(cargada, t)
            self.assertEqual(t.call_args.args[0]['model'], capa['modelo'])
            self.assertEqual(o._config(cargada)['confianza_minima'], 0.9)
            self.assertEqual(ruta.read_bytes(), original)
            self.assertEqual({nombre: ruta.read_bytes() for nombre, ruta in otros.items()}, antes)

    def test_errores_http_reales_sin_leer_cuerpo_y_diagnostico(self):
        import urllib.error
        self.p, self.cfg = lote(2)
        for codigo, categoria in ((401, 'autenticacion'), (402, 'saldo_o_credito'),
                (403, 'acceso_denegado'), (400, 'peticion_o_modelo'),
                (404, 'recurso_o_modelo'), (422, 'peticion_o_capacidades'),
                (429, 'limite_solicitudes'), (500, 'fallo_servicio'), (503, 'fallo_servicio')):
            cuerpo = Mock()
            error = urllib.error.HTTPError(o.ENDPOINT, codigo, 'privado', {}, cuerpo)
            opener = Mock()
            opener.open.side_effect = error
            with self.subTest(codigo=codigo), patch('urllib.request.build_opener', return_value=opener):
                r = self.comparar(transporte=o.solicitar)
                cuerpo.read.assert_not_called()
                self.assertEqual(opener.open.call_count, 1)
                self.assertEqual(r['resultados'][0]['motivo'], f'http_{codigo}')
                self.assertEqual(r['resultados'][0]['diagnostico_error'], categoria)
                self.assertEqual(r['resultados'][1]['diagnostico_error'], 'llamadas_suspendidas')
                self.assertFalse(r['permitir_movimientos'])
                self.assertNotIn('privado', json.dumps(r))
                self.assertTrue(all('propuesta' not in fila for fila in r['resultados']))

    def test_timeout_y_respuesta_incompleta_con_ayuda(self):
        opener = Mock()
        opener.open.side_effect = TimeoutError('dato-privado')
        with patch('urllib.request.build_opener', return_value=opener):
            r = self.comparar(transporte=o.solicitar)
        self.assertEqual(r['resultados'][0]['diagnostico_error'], 'conexion_o_timeout')
        self.assertNotIn('dato-privado', json.dumps(r))
        def incompleta(body, *_):
            r = respuesta(body)
            r['answers'].pop(next(iter(r['answers'])))
            return r
        fila = self.comparar(transporte=incompleta)['resultados'][0]
        self.assertEqual(fila['diagnostico_error'], 'respuesta_invalida_o_incompatible')
        self.assertNotIn('propuesta', fila)

    def test_diagnostico_hibrido_y_exito_sin_ayuda(self):
        self.assertNotIn('diagnostico_error', self.comparar()['resultados'][0])
        for e in self.p['emails']:
            e.pop('principal')
            e['contexto_suficiente'] = True
        t = Mock(side_effect=o.ErrorOpenRouter('http_402'))
        r = o.evaluar(self.p, self.cfg, dict(ACTIVO, modo='hibrido'), t)
        self.assertEqual(r['resultados'][0]['diagnostico_error'], 'saldo_o_credito')
        self.assertFalse(r['permitir_movimientos'])
