"""El informe muestra la alerta de plantilla que se apaga al repuntuar (v3.21.37).

Prueba real 2026-10-24: «6 promos salieron con veredictos idénticos. Los
reexaminé uno a uno y diferencié los que realmente diferían. La alerta
desapareció tras eso». Puede ser honesto o un retoque para callar la
alarma; el informe no lo juzga, lo muestra. Lee el desglose acumulado de la
sesión (`scoring --desglose-append`). Sin red; tempfiles.
"""
import json
import os
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

SID = "20261024-091500"
CFG = {
    "criterios_epistemicos": {
        c: {"activo": True, "core": True, "eje": "valor_decisional",
            "si": 2, "no": -2} for c in ("a", "b", "c")},
    "scoring": {"ejes": {"valor_decisional": [-10, 10]}},
    "tiers": {"reply_needed": 10, "review": 4, "reading_later": 0,
              "archive": -1},
}
IGUALES = {"a": "no", "b": "no", "c": "no"}
UNIDAD = {"n": 1, "tier": "ARCHIVE", "score": -6, "asunto": "Promo",
          "remitente": "p@x.com", "fecha": "24/10", "mids": ["<m1>"],
          "accion": "propuesto"}


def _lote(veredictos):
    return th.cmd_scoring_dispatch(
        {"emails": [{"id": i, "verdicts": v} for i, v in enumerate(veredictos, 1)]},
        CFG)


class TestPlantillaRetocada(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.d.name
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))
        self.ruta = os.path.join(self.d.name, "desgloses", SID + ".jsonl")

    def _pasadas(self, *lotes):
        for salida in lotes:
            r = th.cmd_registrar(self.ruta, {"ts": "2026-10-24T09:15:00+00:00",
                                             "desglose": salida})
            self.assertTrue(r.get("ok"), r)

    def _informe(self):
        r = th.cmd_informe({"session_id": SID, "modo": "simulacion",
                            "modo_scoring": "determinista",
                            "unidades": [dict(UNIDAD)]})
        self.assertTrue(r["ok"], r)
        with open(r["ruta"], encoding="utf-8") as fh:
            return r, fh.read()

    def test_el_caso_real_la_alerta_desaparece(self):
        primera = _lote([IGUALES] * 6)
        self.assertIn("alerta_plantilla", primera)
        retocados = [dict(IGUALES, a="si"), dict(IGUALES, b="si"),
                     dict(IGUALES, c="si"), IGUALES, IGUALES, IGUALES]
        segunda = _lote(retocados)
        self.assertNotIn("alerta_plantilla", segunda)
        self._pasadas(primera, segunda)
        r, md = self._informe()
        self.assertEqual(len(r["plantilla_retocada"]), 6)
        self.assertIn("Alerta de plantilla retocada: 6 correos", md)
        cambio = {x["id"]: x["veredictos_cambiados"]
                  for x in r["plantilla_retocada"]}
        self.assertEqual(cambio[1], ["a"])
        self.assertEqual(cambio[4], [])  # dejó de serlo porque cambiaron otros

    def test_alerta_que_sigue_no_es_retoque(self):
        self._pasadas(_lote([IGUALES] * 6), _lote([IGUALES] * 6))
        r, md = self._informe()
        self.assertEqual(r["plantilla_retocada"], [])
        self.assertNotIn("retocada", md)

    def test_sin_desglose_nada_cambia(self):
        r, md = self._informe()
        self.assertNotIn("plantilla_retocada", r)
        self.assertNotIn("retocada", md)

    def test_desglose_raro_no_rompe_el_informe(self):
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        for basura in ("no es json\n", json.dumps([1, 2]) + "\n",
                       json.dumps({"ts": "x", "desglose": {"resultados": [
                           "texto", {"id": {"a": 1}, "plantilla": True}]}}) + "\n"):
            with open(self.ruta, "w", encoding="utf-8") as fh:
                fh.write(basura)
            r, _ = self._informe()
            self.assertIn(r.get("plantilla_retocada"), (None, []), basura)


if __name__ == "__main__":
    unittest.main()
