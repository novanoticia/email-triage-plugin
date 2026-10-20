"""limpiar-tmp (v3.21.23): el script vacía tmp/ de restos antiguos.

Prueba real 2026-10-20: ~/.email-triage/tmp/ acumulaba 998 entradas
(7,1 MB) de sesiones anteriores; solo los cuerpos crudos se borraban solos.
El margen de edad protege la sesión en curso. Sin red; tempfiles.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

if DIR_SCRIPTS not in sys.path:
    sys.path.insert(0, DIR_SCRIPTS)
import triage_helpers as th  # noqa: E402

SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")
VIEJO = time.time() - 48 * 3600


class TestLimpiarTmp(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.base = os.path.join(self.d.name, "base")
        self.tmp = os.path.join(self.base, "tmp")
        os.makedirs(self.tmp, mode=0o700)
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.base
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))

    def _fichero(self, rel, antiguo=True, texto="x"):
        ruta = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        if antiguo:
            os.utime(ruta, (VIEJO, VIEJO))
        return ruta

    def test_borra_lo_antiguo_y_conserva_lo_reciente(self):
        viejos = [self._fichero("tbody_%d.txt" % i, texto="abc")
                  for i in range(5)]
        nuevo = self._fichero("scoring.json", antiguo=False)
        r = th.cmd_limpiar_tmp()
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["borrados"], r["recientes"]), (5, 1))
        self.assertEqual(r["bytes_liberados"], 15)
        self.assertFalse(any(os.path.exists(v) for v in viejos))
        self.assertTrue(os.path.exists(nuevo))
        self.assertTrue(os.path.isdir(self.tmp))       # tmp/ se conserva

    def test_dry_run_no_borra(self):
        ruta = self._fichero("a.json")
        r = th.cmd_limpiar_tmp(dry_run=True)
        self.assertEqual(r["borrados"], 1)
        self.assertTrue(os.path.exists(ruta))

    def test_no_toca_nada_fuera_de_tmp(self):
        fuera = os.path.join(self.base, "session_log.jsonl")
        with open(fuera, "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        os.utime(fuera, (VIEJO, VIEJO))
        self._fichero("a.json")
        th.cmd_limpiar_tmp()
        self.assertTrue(os.path.exists(fuera))

    def test_borra_el_enlace_no_su_destino(self):
        destino = os.path.join(self.d.name, "importante.txt")
        with open(destino, "w", encoding="utf-8") as fh:
            fh.write("no borrar")
        dir_destino = os.path.join(self.d.name, "carpeta")
        os.makedirs(dir_destino)
        dentro = os.path.join(dir_destino, "dentro.txt")
        with open(dentro, "w", encoding="utf-8") as fh:
            fh.write("no borrar")
        for nombre, apunta in (("enlace", destino), ("enlace_dir", dir_destino)):
            ruta = os.path.join(self.tmp, nombre)
            os.symlink(apunta, ruta)
            os.utime(ruta, (VIEJO, VIEJO), follow_symlinks=False)
        r = th.cmd_limpiar_tmp()
        self.assertEqual(r["borrados"], 2, r)
        self.assertTrue(os.path.exists(destino))
        self.assertTrue(os.path.exists(dentro))
        self.assertFalse(os.path.lexists(os.path.join(self.tmp, "enlace")))

    def test_quita_subcarpetas_vacias_y_conserva_las_que_no(self):
        self._fichero("lote1/a.json")
        self._fichero("lote2/b.json")
        self._fichero("lote2/c.json", antiguo=False)
        for d in ("lote1", "lote2"):
            os.utime(os.path.join(self.tmp, d), (VIEJO, VIEJO))
        th.cmd_limpiar_tmp()
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "lote1")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "lote2", "c.json")))

    def test_carpeta_vacia_reciente_se_conserva(self):
        # Revisión Codex (PR #92): una rutina en paralelo acaba de crearla.
        os.makedirs(os.path.join(self.tmp, "rutina"))
        th.cmd_limpiar_tmp()
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "rutina")))

    def test_carpeta_ilegible_va_a_errores(self):
        # Revisión Codex (PR #92): os.walk la saltaba en silencio.
        from unittest import mock
        self._fichero("sub/a.json")
        real = os.scandir
        llamadas = []

        def falla_en_sub(fd):
            llamadas.append(fd)
            if len(llamadas) > 1:
                raise PermissionError("sin permiso")
            return real(fd)
        with mock.patch.object(th.os, "scandir", falla_en_sub):
            r = th.cmd_limpiar_tmp()
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["errores"]), 1, r)
        self.assertTrue(r["errores"][0]["ruta"].endswith("sub"))

    def test_tmp_como_enlace_no_se_recorre(self):
        fuera = os.path.join(self.d.name, "fuera")
        os.makedirs(fuera)
        viejo_fuera = os.path.join(fuera, "x.txt")
        with open(viejo_fuera, "w", encoding="utf-8") as fh:
            fh.write("no borrar")
        os.utime(viejo_fuera, (VIEJO, VIEJO))
        os.rmdir(self.tmp)
        os.symlink(fuera, self.tmp)
        r = th.cmd_limpiar_tmp()
        self.assertEqual(r["borrados"], 0, r)
        self.assertTrue(os.path.exists(viejo_fuera))

    def test_horas_cero_borra_todo(self):
        self._fichero("a.json", antiguo=False)
        time.sleep(0.01)
        r = th.cmd_limpiar_tmp(horas=0)
        self.assertEqual(r["borrados"], 1, r)

    def test_entradas_invalidas_y_tmp_ausente(self):
        for horas in (-1, "12", True, None, 10 ** 6):
            with self.subTest(horas=horas):
                self.assertFalse(th.cmd_limpiar_tmp(horas=horas)["ok"])
        os.environ[th.ENV_BASE_ESTADO] = os.path.join(self.d.name, "nada")
        r = th.cmd_limpiar_tmp()
        self.assertTrue(r["ok"])
        self.assertEqual(r["borrados"], 0)

    def test_cli(self):
        self._fichero("a.json")
        r = subprocess.run([sys.executable, SCRIPT, "limpiar-tmp",
                            "--dry-run"], capture_output=True, text=True,
                           timeout=30, env=dict(os.environ))
        out = json.loads(r.stdout)
        self.assertEqual((out["borrados"], out["dry_run"]), (1, True))


if __name__ == "__main__":
    unittest.main()
