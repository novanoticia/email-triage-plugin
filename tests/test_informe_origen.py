"""`informe --archivo RUTA --borrar-origen` y aviso `sobrescrito` (v3.22.15).

Prueba real 2026-10-27: el script auxiliar del modelo falló y dejó en tmp/
un informe.json de la sesión anterior; `informe` lo leyó y regeneró el
informe de ESA sesión sin que nada lo dijera. Ahora el JSON puede borrarse
tras usarlo, como los cuerpos crudos de `sanitizar --borrar-origen`, y
sobrescribir un informe existente se avisa. Sin red; tempfiles.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests import DIR_SCRIPTS
from tests.test_informe import _ConHome, unidad
import triage_helpers as th

SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")


class TestInformeOrigen(_ConHome):
    def datos(self, sid="20261027-1024"):
        return {"session_id": sid, "modo": "simulacion",
                "unidades": [unidad(accion="propuesto")]}

    def cli(self, *args):
        r = subprocess.run([sys.executable, SCRIPT, "informe", *args],
                           capture_output=True, text=True,
                           env=dict(os.environ, **{th.ENV_BASE_ESTADO: self.dir}))
        return json.loads(r.stdout)

    def escribir_json(self, datos, nombre="informe.json", dentro=True):
        base = os.path.join(self.dir, "tmp") if dentro else tempfile.mkdtemp()
        os.makedirs(base, exist_ok=True)
        ruta = os.path.join(base, nombre)
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(datos, fh)
        return ruta

    def test_borra_el_json_tras_escribir(self):
        ruta = self.escribir_json(self.datos())
        out = self.cli("--archivo", ruta, "--borrar-origen")
        self.assertTrue(out["ok"], out)
        self.assertFalse(os.path.exists(ruta))
        self.assertTrue(out["origen_borrado"][0]["borrado"])
        self.assertEqual(out["origen_pendiente"], [])

    def test_sin_borrar_origen_el_json_se_queda(self):
        ruta = self.escribir_json(self.datos())
        out = self.cli("--archivo", ruta)
        self.assertTrue(out["ok"], out)
        self.assertTrue(os.path.exists(ruta))
        self.assertNotIn("origen_borrado", out)

    def test_si_falla_no_borra(self):
        ruta = self.escribir_json({"session_id": "../fuera", "modo": "real",
                                   "unidades": []})
        out = self.cli("--archivo", ruta, "--borrar-origen")
        self.assertIs(out["ok"], False)
        self.assertTrue(os.path.exists(ruta))

    def test_fuera_de_tmp_no_se_borra_y_se_dice(self):
        ruta = self.escribir_json(self.datos(), dentro=False)
        out = self.cli("--archivo", ruta, "--borrar-origen")
        self.assertTrue(out["ok"], out)
        self.assertTrue(os.path.exists(ruta))
        self.assertEqual(out["origen_pendiente"], [ruta])

    def test_borrar_origen_sin_archivo_es_error(self):
        out = self.cli("--borrar-origen", "--datos", json.dumps(self.datos()))
        self.assertIs(out["ok"], False)
        self.assertIn("--archivo", out["error"])

    def test_archivo_ilegible(self):
        out = self.cli("--archivo", os.path.join(self.dir, "no-existe.json"))
        self.assertIs(out["ok"], False)

    def test_sobrescribir_se_avisa(self):
        primero = th.cmd_informe(self.datos())
        self.assertTrue(primero["ok"])
        self.assertNotIn("sobrescrito", primero)
        segundo = th.cmd_informe(self.datos())
        self.assertTrue(segundo["ok"])
        self.assertIn("mtime_anterior", segundo["sobrescrito"])
        # Otra sesión no avisa: es un fichero distinto.
        self.assertNotIn("sobrescrito", th.cmd_informe(self.datos("20261027-1100")))

    def test_stdin_sigue_igual(self):
        r = subprocess.run([sys.executable, SCRIPT, "informe"],
                           input=json.dumps(self.datos()), capture_output=True,
                           text=True,
                           env=dict(os.environ, **{th.ENV_BASE_ESTADO: self.dir}))
        out = json.loads(r.stdout)
        self.assertTrue(out["ok"], out)
        self.assertNotIn("origen_borrado", out)


if __name__ == "__main__":
    unittest.main()
