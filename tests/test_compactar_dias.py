"""compactar --dias (v3.22.8): retención por fecha del session log.

Prueba real 2026-10-26: el SKILL.md mandaba purgar las entradas de más de 30
días y `compactar` solo recortaba por número de líneas, así que el modelo
reescribió session_log.jsonl con un script propio. Ahora la purga por fecha
pasa por el mismo camino atómico y bloqueado que `compactar`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from tests import DIR_SCRIPTS
import triage_helpers as th

AHORA = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def iso(dias_atras, campo="ts"):
    return {campo: (AHORA - timedelta(days=dias_atras)).isoformat()}


class TestCompactarDias(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ruta = os.path.join(self.dir, "session_log.jsonl")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def escribir(self, lineas):
        with open(self.ruta, "w", encoding="utf-8") as fh:
            for ln in lineas:
                fh.write((ln if isinstance(ln, str) else json.dumps(ln)) + "\n")

    def leer(self):
        with open(self.ruta, encoding="utf-8") as fh:
            return fh.read().splitlines()

    def test_purga_solo_lo_antiguo_y_conserva_el_orden(self):
        lineas = [dict(iso(40), n=1), dict(iso(10), n=2), dict(iso(31), n=3),
                  dict(iso(0), n=4)]
        self.escribir(lineas)
        out = th.cmd_compactar(self.ruta, dias=30, ahora=AHORA)
        self.assertTrue(out["ok"], out)
        self.assertEqual((out["lineas_antes"], out["eliminadas"]), (4, 2))
        self.assertEqual([json.loads(ln)["n"] for ln in self.leer()], [2, 4])

    def test_conserva_lo_que_no_sabe_fechar(self):
        # Sin fecha legible, no JSON o fecha futura: no se sabe antiguo.
        lineas = [iso(90), {"n": "sin_ts"}, "no es json", {"ts": "ayer"},
                  iso(-2), iso(60, "ts_registro")]
        self.escribir(lineas)
        out = th.cmd_compactar(self.ruta, dias=30, ahora=AHORA)
        self.assertEqual(out["eliminadas"], 2, out)
        restantes = self.leer()
        self.assertIn("no es json", restantes)
        self.assertEqual(len(restantes), 4)

    def test_ts_registro_cuenta_si_falta_ts(self):
        self.escribir([iso(45, "ts_registro"), iso(5, "ts_registro")])
        out = th.cmd_compactar(self.ruta, dias=30, ahora=AHORA)
        self.assertEqual(out["eliminadas"], 1, out)

    def test_manda_ts_registro_sobre_ts(self):
        # Revisión Codex P1 (PR #125): un `ts` del modelo antiguo o erróneo
        # no puede purgar una línea recién registrada, y al revés.
        reciente_con_ts_viejo = {"ts": "1999-01-01T00:00:00",
                                 "ts_registro": AHORA.isoformat(), "n": 1}
        vieja_con_ts_nuevo = dict(iso(40, "ts_registro"), ts=AHORA.isoformat(), n=2)
        self.escribir([reciente_con_ts_viejo, vieja_con_ts_nuevo])
        out = th.cmd_compactar(self.ruta, dias=30, ahora=AHORA)
        self.assertEqual(out["eliminadas"], 1, out)
        self.assertEqual([json.loads(ln)["n"] for ln in self.leer()], [1])

    def test_ts_registro_ilegible_cae_a_ts(self):
        self.escribir([dict(iso(40), ts_registro="basura"), dict(iso(1), ts_registro="basura")])
        out = th.cmd_compactar(self.ruta, dias=30, ahora=AHORA)
        self.assertEqual(out["eliminadas"], 1, out)

    def test_dias_ignora_el_tope_de_lineas(self):
        self.escribir([dict(iso(1), n=i) for i in range(50)])
        out = th.cmd_compactar(self.ruta, max_lineas=5, dias=30, ahora=AHORA)
        self.assertFalse(out["cambio"], out)
        self.assertEqual(len(self.leer()), 50)

    def test_nada_antiguo_no_reescribe(self):
        self.escribir([iso(1), iso(2)])
        antes = os.stat(self.ruta).st_ino
        out = th.cmd_compactar(self.ruta, dias=30, ahora=AHORA)
        self.assertFalse(out["cambio"])
        self.assertIn("30 días", out["nota"])
        self.assertEqual(os.stat(self.ruta).st_ino, antes)

    def test_dry_run_no_escribe(self):
        self.escribir([iso(40), iso(1)])
        out = th.cmd_compactar(self.ruta, dias=30, ahora=AHORA, dry_run=True)
        self.assertTrue(out["dry_run"])
        self.assertEqual(out["eliminadas"], 1)
        self.assertEqual(len(self.leer()), 2)

    def test_permisos_600(self):
        self.escribir([iso(40), iso(1)])
        th.cmd_compactar(self.ruta, dias=30, ahora=AHORA)
        self.assertEqual(os.stat(self.ruta).st_mode & 0o777, 0o600)

    def test_dias_invalidos(self):
        self.escribir([iso(40)])
        for malo in (0, -1, True, 1.5, "30"):
            with self.subTest(dias=malo):
                out = th.cmd_compactar(self.ruta, dias=malo, ahora=AHORA)
                self.assertFalse(out["ok"])
        self.assertEqual(len(self.leer()), 1)

    def test_cli(self):
        # Fechas relativas a hoy: el CLI usa la hora real.
        ahora = datetime.now(timezone.utc)
        with open(self.ruta, "w", encoding="utf-8") as fh:
            for d in (40, 1):
                fh.write(json.dumps({"ts": (ahora - timedelta(days=d)).isoformat()}) + "\n")
        r = subprocess.run([sys.executable, os.path.join(DIR_SCRIPTS, "triage_helpers.py"),
                            "compactar", "--archivo", self.ruta, "--dias", "30"],
                           capture_output=True, text=True)
        out = json.loads(r.stdout)
        self.assertTrue(out["ok"], r.stderr)
        self.assertEqual(out["eliminadas"], 1)


if __name__ == "__main__":
    unittest.main()
