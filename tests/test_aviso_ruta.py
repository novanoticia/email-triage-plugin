"""aviso_ruta (v3.21.21): registrar avisa si escribe fuera de la base.

Prueba real 1: el modelo registró los movimientos en una ruta equivocada y
luego copió las líneas a mano al log real. `registrar` sigue escribiendo
(aditivo), pero añade `aviso_ruta` cuando la ruta queda fuera de
base_estado(). Sin red; tempfiles.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

if DIR_SCRIPTS not in sys.path:
    sys.path.insert(0, DIR_SCRIPTS)
import triage_helpers as th  # noqa: E402

SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")
REG = {"session_id": "20261020-120000", "event": "nota"}


class TestAvisoRuta(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.base = os.path.join(self.d.name, "base")
        self.fuera = os.path.join(self.d.name, "otra")
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.base
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))

    def test_dentro_de_la_base_no_avisa(self):
        for rel in ("session_log.jsonl", "desgloses/s.jsonl"):
            with self.subTest(rel=rel):
                r = th.cmd_registrar(os.path.join(self.base, rel), REG)
                self.assertTrue(r["ok"], r)
                self.assertNotIn("aviso_ruta", r)

    def test_fuera_escribe_pero_avisa(self):
        ruta = os.path.join(self.fuera, "session_log.jsonl")
        r = th.cmd_registrar(ruta, REG)
        self.assertTrue(r["ok"], r)
        self.assertIn("fuera de la base de estado", r["aviso_ruta"])
        with open(ruta, encoding="utf-8") as fh:
            self.assertEqual(len(fh.readlines()), 1)     # sí escribió

    def test_prefijo_parecido_no_cuenta_como_dentro(self):
        # <base>-copia empieza igual que <base> pero no está dentro.
        r = th.cmd_registrar(self.base + "-copia/session_log.jsonl", REG)
        self.assertIn("aviso_ruta", r)

    def test_symlink_que_sale_de_la_base_avisa(self):
        os.makedirs(self.base)
        os.makedirs(self.fuera)
        enlace = os.path.join(self.base, "enlace")
        os.symlink(self.fuera, enlace)
        r = th.cmd_registrar(os.path.join(enlace, "log.jsonl"), REG)
        self.assertIn("aviso_ruta", r)

    def test_cerrar_lote_propaga_el_aviso(self):
        ruta = os.path.join(self.fuera, "session_log.jsonl")
        salida = ("movidos_review:1/1 movidos_archive:0/0 "
                  "archivo_nativo_fallido:0 | fallidos_review:[] "
                  "fallidos_archive:[] | src_restantes:0")
        r = th.cmd_cerrar_lote(ruta, {"session_id": REG["session_id"],
                                      "salida": salida})
        self.assertTrue(r["ok"], r)
        self.assertIn("aviso_ruta", r)

    def test_base_en_la_raiz_contiene_todo(self):
        # Revisión Codex (PR #90): con base `/`, base + os.sep era `//`.
        os.environ[th.ENV_BASE_ESTADO] = os.sep
        r = th.cmd_registrar(os.path.join(self.fuera, "log.jsonl"), REG)
        self.assertNotIn("aviso_ruta", r)

    def test_vectores_propaga_el_aviso(self):
        # Revisión Codex (PR #90): vectores construía su propio resultado.
        cfg = {"criterios_epistemicos": {
                   "a": {"activo": True, "core": True,
                         "eje": "valor_decisional", "si": 1, "no": 0}},
               "scoring": {"ejes": {"valor_decisional": [-10, 10]}}}
        desglose = os.path.join(self.base, "desglose.jsonl")
        th.cmd_registrar(desglose, {"ts": "t", "desglose": th.cmd_scoring_dispatch(
            {"emails": [{"id": 1, "verdicts": {"a": "si"}}]}, cfg)})
        r = th.cmd_vectores(os.path.join(self.fuera, "vectors.jsonl"),
                            desglose, {"session_id": REG["session_id"],
                                       "message_ids": {"1": "<m1>"}}, cfg)
        self.assertEqual(r["escritos"], 1, r)
        self.assertIn("aviso_ruta", r)

    def test_cli(self):
        ruta = os.path.join(self.fuera, "x.jsonl")
        r = subprocess.run([sys.executable, SCRIPT, "registrar", "--ruta",
                            ruta, "--registro", json.dumps(REG)],
                           capture_output=True, text=True, timeout=30,
                           env=dict(os.environ))
        self.assertIn("aviso_ruta", json.loads(r.stdout))


if __name__ == "__main__":
    unittest.main()
