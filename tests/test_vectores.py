"""vectores (v3.21.19): vectors.jsonl lo escribe el script desde el desglose.

Prueba real 1: el modelo escribió un vector aproximado por eje y luego borró
esas líneas a mano, justo la reescritura de un JSONL que las invariantes
prohíben. Ahora el vector se deriva del desglose del scoring y `registrar`
rechaza escribir vectors.jsonl a mano. Sin red; tempfiles.
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
SID = "20261020-100000"
CFG = {
    "criterios_epistemicos": {
        "a": {"activo": True, "core": True, "eje": "valor_decisional",
              "si": 2, "no": -2},
        "b": {"activo": True, "core": True, "eje": "calidad_epistemica",
              "si": 1, "no": 0},
        "c": {"activo": True, "core": False, "eje": "calidad_epistemica",
              "si": 1, "no": 0},
        "d": {"activo": False, "core": False, "eje": "calidad_epistemica",
              "si": 1, "no": 0},
    },
    "scoring": {"ejes": {"valor_decisional": [-10, 10],
                         "calidad_epistemica": [-10, 10]}},
    "tiers": {"REVIEW": 2, "READING_LATER": 0},
}


class TestVectores(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.ruta = os.path.join(self.d.name, "vectors.jsonl")
        self.desglose = os.path.join(self.d.name, "desglose.jsonl")

    def _puntuar(self, *emails):
        """Una invocación de `scoring --desglose-append`."""
        out = th.cmd_scoring_dispatch({"emails": list(emails)}, CFG)
        th.cmd_registrar(self.desglose, {"ts": "t", "desglose": out})

    def _lineas(self):
        try:
            with open(self.ruta, encoding="utf-8") as fh:
                return [json.loads(x) for x in fh]
        except OSError:
            return []

    def _vectores(self, mapa):
        return th.cmd_vectores(self.ruta, self.desglose,
                               {"session_id": SID, "message_ids": mapa}, CFG)

    def test_deriva_el_vector_por_criterio(self):
        self._puntuar({"id": 1, "verdicts": {"a": "si", "b": "no"}})
        r = self._vectores({"1": "<m1>"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["escritos"], 1)
        [v] = self._lineas()
        self.assertEqual(v["message_id"], "<m1>")
        self.assertEqual(v["origen"], "vectores")
        self.assertEqual(v["criterios"], {"a": 1, "b": 1, "c": 0})
        self.assertEqual(v["veredictos"], {"a": "si", "b": "no"})
        self.assertEqual(v["score_final"], 2)
        self.assertIn("ts_registro", v)

    def test_manda_la_ultima_pasada(self):
        self._puntuar({"id": 1, "verdicts": {"a": "no", "b": "no"}})
        self._puntuar({"id": 1, "verdicts": {"a": "si", "b": "si", "c": "si"}})
        self._vectores({"1": "<m1>"})
        [v] = self._lineas()
        self.assertEqual(v["veredictos"]["a"], "si")
        self.assertEqual(v["criterios"]["c"], 1)

    def test_hilo_da_una_linea_por_correo(self):
        self._puntuar({"id": "h1", "verdicts": {"a": "si", "b": "si"}})
        r = self._vectores({"h1": ["<m1>", "<m2>"]})
        self.assertEqual(r["escritos"], 2)
        self.assertEqual([v["message_id"] for v in self._lineas()],
                         ["<m1>", "<m2>"])

    def test_omite_vector_incompleto_o_sin_desglose(self):
        # Solo metadatos: falta el core `b`; el id 9 nunca se puntuó.
        self._puntuar({"id": 1, "verdicts": {"a": "si"}})
        r = self._vectores({"1": "<m1>", "9": "<m9>"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["escritos"], 0)
        motivos = {o["id"]: o["motivo"] for o in r["omitidos"]}
        self.assertIn("core", motivos["1"])
        self.assertIn("sin desglose", motivos["9"])
        self.assertEqual(self._lineas(), [])

    def test_omite_plantilla(self):
        iguales = [{"id": i, "verdicts": {"a": "si", "b": "si", "c": "no",
                                          "x1": 1, "x2": 1}}
                   for i in range(th.UMBRAL_PLANTILLA)]
        self._puntuar(*iguales)
        r = self._vectores({"0": "<m0>"})
        self.assertEqual(r["omitidos"][0]["motivo"], "veredictos de plantilla")

    def test_repetir_no_duplica(self):
        self._puntuar({"id": 1, "verdicts": {"a": "si", "b": "si"}})
        self._vectores({"1": "<m1>"})
        r = self._vectores({"1": "<m1>"})
        self.assertEqual((r["escritos"], r["ya_registrados"]), (0, ["<m1>"]))
        self.assertEqual(len(self._lineas()), 1)

    def test_entradas_invalidas_no_escriben(self):
        self._puntuar({"id": 1, "verdicts": {"a": "si", "b": "si"}})
        for datos in (None, [], {"message_ids": {"1": "<m1>"}},
                      {"session_id": SID}, {"session_id": SID,
                                            "message_ids": {}},
                      {"session_id": SID, "message_ids": {"1": ""}},
                      {"session_id": SID, "message_ids": {"1": 3}}):
            with self.subTest(datos=datos):
                r = th.cmd_vectores(self.ruta, self.desglose, datos, CFG)
                self.assertFalse(r["ok"], r)
        r = th.cmd_vectores(self.ruta, os.path.join(self.d.name, "no"),
                            {"session_id": SID, "message_ids": {"1": "<m>"}},
                            CFG)
        self.assertFalse(r["ok"])
        self.assertEqual(self._lineas(), [])

    def test_registrar_rechaza_vectores_a_mano(self):
        r = th.cmd_registrar(self.ruta, {"session_id": SID,
                                         "message_id": "<m1>",
                                         "criterios": {"a": 1}})
        self.assertFalse(r["ok"])
        self.assertIn("vectores", r["remedio"])
        self.assertEqual(self._lineas(), [])
        # Otros JSONL de telemetría siguen igual.
        otro = os.path.join(self.d.name, "scores.jsonl")
        self.assertTrue(th.cmd_registrar(otro, {"session_id": SID})["ok"])

    def test_desglose_demasiado_grande_es_error(self):
        # Revisión Codex (PR #88): leído a medias perdería la última pasada.
        self._puntuar({"id": 1, "verdicts": {"a": "si", "b": "si"}})
        viejo = th.MAX_INGESTA_BYTES
        th.MAX_INGESTA_BYTES = 10
        try:
            r = self._vectores({"1": "<m1>"})
        finally:
            th.MAX_INGESTA_BYTES = viejo
        self.assertFalse(r["ok"])
        self.assertEqual(self._lineas(), [])

    def test_criterio_con_clave_no_cadena_no_revienta(self):
        crits = dict(CFG["criterios_epistemicos"])
        crits[1] = {"activo": True, "core": True}
        cfg = {"criterios_epistemicos": crits}
        self._puntuar({"id": 1, "verdicts": {"a": "si", "b": "si"}})
        r = th.cmd_vectores(self.ruta, self.desglose,
                            {"session_id": SID, "message_ids": {"1": "<m>"}},
                            cfg)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["escritos"], 1)

    def test_snapshot_no_pisa_vectors(self):
        # Revisión Codex (PR #88): `scoring --desglose vectors.jsonl` o
        # `calibrar --guardar` lo reemplazarían entero.
        self._puntuar({"id": 1, "verdicts": {"a": "si", "b": "si"}})
        self._vectores({"1": "<m1>"})
        r = th._escribir_snapshot_json({"x": 1}, self.ruta, ".t-")
        self.assertFalse(r["ok"])
        self.assertEqual(len(self._lineas()), 1)

    def test_cli_aplica_las_capas_del_scoring(self):
        # Revisión Codex (PR #88): con el ensayo P3 cambian los core; sin
        # la capa, todo vector saldría incompleto.
        self._puntuar({"id": 1, "verdicts": {"a": "si", "c": "si"}})
        d = self.d.name
        cfg, capa = os.path.join(d, "config.yaml"), os.path.join(d, "e.yaml")
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump(CFG, fh)
        with open(capa, "w", encoding="utf-8") as fh:
            json.dump({"criterios_epistemicos": {
                "b": {"activo": False}, "c": {"core": True}}}, fh)
        datos = json.dumps({"session_id": SID, "message_ids": {"1": "<m1>"}})
        base = [sys.executable, SCRIPT, "vectores", "--ruta", self.ruta,
                "--desglose", self.desglose, "--config", cfg, "--datos", datos]
        sin = json.loads(subprocess.run(base, capture_output=True, text=True,
                                        timeout=30).stdout)
        if "PyYAML" in json.dumps(sin, ensure_ascii=False):
            self.skipTest("sin PyYAML")
        self.assertEqual(sin["escritos"], 0)            # falta el core b
        con = json.loads(subprocess.run(base + ["--config-ensayo", capa],
                                        capture_output=True, text=True,
                                        timeout=30).stdout)
        self.assertEqual(con["escritos"], 1, con)

    def test_cli(self):
        self._puntuar({"id": 1, "verdicts": {"a": "si", "b": "si"}})
        cfg = os.path.join(self.d.name, "config.yaml")
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump(CFG, fh)            # JSON es YAML válido
        datos = json.dumps({"session_id": SID, "message_ids": {"1": "<m1>"}})
        base = [sys.executable, SCRIPT, "vectores", "--ruta", self.ruta,
                "--desglose", self.desglose, "--config", cfg, "--datos"]
        r = subprocess.run(base + [datos], capture_output=True, text=True,
                           timeout=30)
        out = json.loads(r.stdout)
        if "PyYAML" in json.dumps(out, ensure_ascii=False):
            self.skipTest("sin PyYAML")
        self.assertTrue(out["ok"], out)
        r = subprocess.run(base + ["{no json"], capture_output=True,
                           text=True, timeout=30)
        self.assertFalse(json.loads(r.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
