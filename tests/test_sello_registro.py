"""Sello `ts_registro` de registrar (v3.21.15).

El `ts` de un movimiento lo escribe el modelo, sin zona fiable: no sirvió
para el corte `legado` de v3.21.14. Fija: registrar añade a CADA línea la
hora real del append en UTC, pisa un `ts_registro` falsificado y no toca
`ts` ni el resto de campos. Sin red; tempfiles.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

if DIR_SCRIPTS not in sys.path:
    sys.path.insert(0, DIR_SCRIPTS)
import triage_helpers as th  # noqa: E402


class TestSelloRegistro(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.ruta = os.path.join(self.d.name, "log.jsonl")

    def _lineas(self):
        with open(self.ruta, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh.read().splitlines() if l]

    def test_sella_en_utc_y_conserva_el_resto(self):
        antes = datetime.now(timezone.utc).replace(microsecond=0)
        reg = {"session_id": "s", "ts": "2026-10-19T09:00:00", "x": 1}
        self.assertTrue(th.cmd_registrar(self.ruta, reg)["ok"])
        (linea,) = self._lineas()
        sello = datetime.fromisoformat(linea.pop("ts_registro"))
        self.assertEqual(sello.utcoffset(), timedelta(0))
        self.assertTrue(antes <= sello <= antes + timedelta(seconds=5))
        self.assertEqual(linea, reg)                # ts del modelo intacto
        self.assertNotIn("ts_registro", reg)        # no muta la entrada

    def test_un_sello_falsificado_se_pisa(self):
        th.cmd_registrar(self.ruta, {"ts_registro": "2020-01-01T00:00:00+00:00"})
        self.assertNotEqual(self._lineas()[0]["ts_registro"],
                            "2020-01-01T00:00:00+00:00")

    def test_el_cierre_tambien_se_sella(self):
        out = th.cmd_cerrar_lote(self.ruta, {"session_id": "20261019-090000",
                                             "salida": "movidos_review:1/1"})
        self.assertTrue(out["ok"], out)
        self.assertIn("ts_registro", self._lineas()[0])

    def test_el_sello_se_toma_con_el_lock_puesto(self):
        # Revisión: sellado antes del flock, dos registrar en competencia
        # podían dejar las horas en otro orden que las líneas.
        import fcntl
        orden = []
        flock_real = fcntl.flock

        def flock(fd, op):
            if op == fcntl.LOCK_EX:
                orden.append("lock")
            return flock_real(fd, op)

        class Reloj(datetime):
            @classmethod
            def now(cls, tz=None):
                orden.append("sello")
                return datetime.now(tz)

        with mock.patch("fcntl.flock", side_effect=flock), \
                mock.patch.object(th, "datetime", Reloj):
            self.assertTrue(th.cmd_registrar(self.ruta, {"x": 1})["ok"])
        self.assertEqual(orden, ["lock", "sello"])

    def test_desglose_de_una_pasada_sellado_sigue_siendo_jsonl(self):
        doc = {"ts": "t", "desglose": {"a": 1}, "ts_registro": "t2"}
        r = th._parsear_desglose(json.dumps(doc))
        self.assertEqual(r["pasadas"], [{"a": 1}])


if __name__ == "__main__":
    unittest.main()
