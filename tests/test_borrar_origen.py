"""sanitizar --borrar-origen (v3.21.11): el cuerpo crudo no sobrevive.

Pruebas reales 6 y 12 (2026-10-18): quedaron cuerpos crudos en tmp/ porque
la limpieza dependía de que el modelo la hiciera al final. Fija: borra
cuerpo y metadatos tras sanear, solo dentro de <base>/tmp/; nada fuera; nada
si los metadatos están rotos; sin el flag no borra. Sin red; tempfiles.
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

SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")


class TestBorrarOrigen(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.base = os.path.join(self.d.name, "estado")
        self.tmp = os.path.join(self.base, "tmp")
        os.makedirs(self.tmp)

    def _fichero(self, directorio, nombre, texto):
        ruta = os.path.join(directorio, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
        return ruta

    def _sanitizar(self, *args):
        env = dict(os.environ, EMAIL_TRIAGE_HOME=self.base)
        p = subprocess.run([sys.executable, SCRIPT, "sanitizar", *args],
                           capture_output=True, text=True, timeout=60, env=env)
        return json.loads(p.stdout)

    def test_borra_cuerpo_y_metadatos_dentro_de_tmp(self):
        cuerpo = self._fichero(self.tmp, "tbody_1.txt", "Hola, texto normal.")
        meta = self._fichero(self.tmp, "meta_1.json",
                             json.dumps({"asunto": "A", "remitente": "B"}))
        r = self._sanitizar("--archivo", cuerpo, "--metadatos", meta,
                            "--borrar-origen")
        self.assertIn("texto", r)
        self.assertEqual([x["borrado"] for x in r["origen_borrado"]], [True, True])
        self.assertFalse(os.path.exists(cuerpo))
        self.assertFalse(os.path.exists(meta))

    def test_sin_el_flag_no_borra(self):
        cuerpo = self._fichero(self.tmp, "tbody_2.txt", "texto")
        r = self._sanitizar("--archivo", cuerpo)
        self.assertNotIn("origen_borrado", r)
        self.assertTrue(os.path.exists(cuerpo))

    def test_nunca_fuera_de_tmp(self):
        fuera = self._fichero(self.d.name, "importante.txt", "no me borres")
        r = self._sanitizar("--archivo", fuera, "--borrar-origen")
        self.assertIs(r["origen_borrado"][0]["borrado"], False)
        self.assertTrue(os.path.exists(fuera))

    def test_symlink_en_tmp_hacia_fuera_no_se_sigue(self):
        fuera = self._fichero(self.d.name, "importante.txt", "no me borres")
        enlace = os.path.join(self.tmp, "tbody_3.txt")
        os.symlink(fuera, enlace)
        r = self._sanitizar("--archivo", enlace, "--borrar-origen")
        self.assertIs(r["origen_borrado"][0]["borrado"], False)
        self.assertTrue(os.path.exists(fuera))

    def test_metadatos_rotos_no_borran_nada(self):
        cuerpo = self._fichero(self.tmp, "tbody_4.txt", "texto")
        meta = self._fichero(self.tmp, "meta_4.json", "{roto")
        r = self._sanitizar("--archivo", cuerpo, "--metadatos", meta,
                            "--borrar-origen")
        self.assertIs(r["ok"], False)
        self.assertTrue(os.path.exists(cuerpo))
        self.assertTrue(os.path.exists(meta))

    def test_el_skill_lo_usa(self):
        with open(os.path.join(os.path.dirname(DIR_SCRIPTS), "SKILL.md"),
                  encoding="utf-8") as f:
            self.assertIn("--borrar-origen", f.read())


if __name__ == "__main__":
    unittest.main()
