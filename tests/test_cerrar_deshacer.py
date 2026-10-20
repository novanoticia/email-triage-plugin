"""cerrar-deshacer (v3.21.18): el resultado del deshacer lo registra el script.

Prueba real 2: el modelo anotó a mano un `undone` en la sesión equivocada.
Ahora cada correo se comprueba contra el log (es de esa sesión y es
deshacible) antes de escribir nada, y `registrar` rechaza los eventos de
deshacer escritos a mano. Sin red; tempfiles.
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
S1, S2 = "20261019-100000", "20261019-110000"


def _mov(sid, mid):
    return {"session_id": sid, "ts": "2026-10-19T10:00", "message_id": mid,
            "subject": "Asunto " + mid, "from_folder": "INBOX",
            "to_folder": "Archive", "tier": "ARCHIVE", "score": 1,
            "modo_scoring": "determinista", "status": "pending"}


def _cierre(sid, n_ok, fallidos=()):
    return {"session_id": sid, "event": th.EVENTO_CIERRE, "n_ok": n_ok,
            "n_lanzados": n_ok + len(fallidos), "fallidos": list(fallidos)}


class TestCerrarDeshacer(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.ruta = os.path.join(self.d.name, "session_log.jsonl")
        self._log(_mov(S1, "a"), _mov(S1, "b"), _mov(S1, "c"),
                  _cierre(S1, 3), _mov(S2, "x"), _cierre(S2, 1))

    def _log(self, *regs):
        with open(self.ruta, "w", encoding="utf-8") as fh:
            for r in regs:
                fh.write(json.dumps(r) + "\n")

    def _lineas(self):
        with open(self.ruta, encoding="utf-8") as fh:
            return fh.read().splitlines()

    def _cerrar(self, **datos):
        return th.cmd_cerrar_deshacer(self.ruta, dict(session_id=S1, **datos))

    def test_registra_una_linea_y_estado_log_la_aplica(self):
        antes = len(self._lineas())
        r = self._cerrar(revertidos=["a"], fallidos=["b"])
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["n_revertidos"], r["n_fallidos"]), (1, 1))
        self.assertEqual(r["deshacibles_restantes"], 2)
        lineas = self._lineas()
        self.assertEqual(len(lineas), antes + 1)     # una sola línea
        ev = json.loads(lineas[-1])
        self.assertEqual(ev["event"], "undo_batch_done")
        self.assertEqual(ev["origen"], "cerrar-deshacer")
        self.assertIn("ts_registro", ev)
        est = {c["message_id"]: (c["estado"], c["deshacible"])
               for c in th.cmd_estado_log(self.ruta, S1)["correos"]}
        self.assertEqual(est, {"a": ("deshecho", False),
                               "b": ("undo_fallido", True),
                               "c": ("movido", True)})

    def test_correo_de_otra_sesion_no_escribe_nada(self):
        # El incidente de la prueba real 2: `x` es de S2, no de S1.
        antes = self._lineas()
        r = self._cerrar(revertidos=["a", "x"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["ajenos"], ["x"])
        self.assertEqual(self._lineas(), antes)

    def test_no_deshacible_no_escribe_nada(self):
        # d está en los `fallidos` del cierre: nunca se movió.
        self._log(_mov(S1, "a"), _mov(S1, "d"), _cierre(S1, 1, ["d"]))
        antes = self._lineas()
        r = self._cerrar(revertidos=["a", "d"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["no_deshacibles"],
                         [{"message_id": "d", "estado": "fallido"}])
        self.assertEqual(self._lineas(), antes)

    def test_ya_deshecho_es_idempotente(self):
        self.assertTrue(self._cerrar(revertidos=["a"])["ok"])
        antes = self._lineas()
        r = self._cerrar(revertidos=["a"])
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["escrito"])
        self.assertEqual(r["ya_deshechos"], ["a"])
        self.assertEqual(self._lineas(), antes)

    def test_deshacer_solapados_conservan_sus_exitos(self):
        # Revisión Codex (PR #87): A revierte a y falla b; B revierte b y
        # falla a. B no debe perder su éxito en b.
        self.assertTrue(self._cerrar(revertidos=["a"], fallidos=["b"])["ok"])
        r = self._cerrar(revertidos=["b"], fallidos=["a"])
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["ya_deshechos"], ["a"])
        est = {c["message_id"]: c["estado"]
               for c in th.cmd_estado_log(self.ruta, S1)["correos"]}
        self.assertEqual((est["a"], est["b"]), ("deshecho", "deshecho"))

    def test_linea_de_deshacer_mal_formada_se_ignora(self):
        # Revisión Codex (PR #87): estado-log es total.
        with open(self.ruta, "a", encoding="utf-8") as fh:
            for malo in (1, "abc", {"a": 1}, None):
                fh.write(json.dumps({"event": "undo_batch_done",
                                     "session_id": S1, "revertidos": malo,
                                     "fallidos": malo}) + "\n")
        r = th.cmd_estado_log(self.ruta, S1)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["deshacibles"], 3)
        self.assertTrue(self._cerrar(revertidos=["a"])["ok"])

    def test_sesion_sin_cerrar_exige_el_opt_in(self):
        s3 = "20261019-120000"
        with open(self.ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(_mov(s3, "z")) + "\n")
        r = th.cmd_cerrar_deshacer(self.ruta, {"session_id": s3,
                                               "revertidos": ["z"]})
        self.assertFalse(r["ok"])
        self.assertEqual(r["no_deshacibles"][0]["estado"], "registrado")
        r = th.cmd_cerrar_deshacer(self.ruta, {"session_id": s3,
                                               "revertidos": ["z"],
                                               "incluir_sin_cerrar": True})
        self.assertTrue(r["ok"], r)

    def test_entradas_invalidas(self):
        for datos in (None, [], {"revertidos": ["a"]},
                      {"session_id": S1},
                      {"session_id": S1, "revertidos": "a"},
                      {"session_id": S1, "revertidos": ["a", "a"]},
                      {"session_id": S1, "revertidos": [""]},
                      {"session_id": S1, "revertidos": ["a"],
                       "fallidos": ["a"]},
                      {"session_id": S1, "revertidos": ["a"],
                       "incluir_sin_cerrar": "true"},
                      {"session_id": "20991231-000000", "revertidos": ["a"]}):
            with self.subTest(datos=datos):
                antes = self._lineas()
                r = th.cmd_cerrar_deshacer(self.ruta, datos)
                self.assertFalse(r["ok"], r)
                self.assertIn("error", r)
                self.assertEqual(self._lineas(), antes)

    def test_registrar_rechaza_deshacer_a_mano(self):
        antes = self._lineas()
        for ev in ("undone", "undo_failed", "undo_batch_done"):
            with self.subTest(ev=ev):
                r = th.cmd_registrar(self.ruta, {
                    "event": ev, "session_id": S1, "message_id": "a",
                    "revertidos": ["a"], "origen": "cerrar-deshacer"})
                self.assertFalse(r["ok"])
                self.assertIn("cerrar-deshacer", r["remedio"])
        self.assertEqual(self._lineas(), antes)

    def test_los_undone_legados_se_siguen_leyendo(self):
        # Logs anteriores a v3.21.18 traen un `undone` por correo.
        with open(self.ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"event": "undone", "session_id": S1,
                                 "message_id": "c"}) + "\n")
        est = {c["message_id"]: c["estado"]
               for c in th.cmd_estado_log(self.ruta, S1)["correos"]}
        self.assertEqual(est["c"], "deshecho")

    def test_cli(self):
        datos = json.dumps({"session_id": S1, "revertidos": ["b"]})
        r = subprocess.run([sys.executable, SCRIPT, "cerrar-deshacer",
                            "--ruta", self.ruta, "--datos", datos],
                           capture_output=True, text=True, timeout=30)
        out = json.loads(r.stdout)
        self.assertTrue(out["ok"], out)
        r = subprocess.run([sys.executable, SCRIPT, "cerrar-deshacer",
                            "--ruta", self.ruta, "--datos", "{no json"],
                           capture_output=True, text=True, timeout=30)
        self.assertFalse(json.loads(r.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
