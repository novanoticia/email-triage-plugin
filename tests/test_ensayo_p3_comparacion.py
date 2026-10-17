"""Comparación base / ensayo P3 sobre los correos ficticios (PR-C2).

Fija la forma del fichero de correos (sin datos reales, grupos de veredictos
separados), que el script puntúa sin veredictos ignorados, y que la tabla de
docs/ensayo-p3-resultados.md es exactamente la que produce el script: las
cifras del informe no pueden desfasarse. Solo stdlib + PyYAML; sin red.
"""
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

RUTA_DOC = os.path.join(_RAIZ, "docs", "ensayo-p3-resultados.md")
SUSTITUIDOS = {"forward_backward_flow", "fake_justification", "third_alternative"}
NUEVOS = {"razonamiento_dirigido", "alternativas_reales", "responsabilidad_personal"}


@unittest.skipIf(yaml is None, "PyYAML no instalado")
class TestComparacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(_RAIZ, "scripts"))
        import ensayo_p3_comparar as cmp
        cls.cmp = cmp
        cls.res = cmp.comparar()
        with open(cmp.RUTA_CORREOS, encoding="utf-8") as f:
            cls.correos = yaml.safe_load(f)["correos"]

    def test_correos_ficticios_y_grupos_separados(self):
        ids = [c["id"] for c in self.correos]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 8)
        for c in self.correos:
            self.assertRegex(c["remitente"], r"@[a-z0-9.-]+\.example>$", c["id"])
            self.assertLessEqual(set(c.get("base") or {}), SUSTITUIDOS, c["id"])
            self.assertLessEqual(set(c.get("ensayo") or {}), NUEVOS, c["id"])
            self.assertFalse(set(c["comunes"]) & (SUSTITUIDOS | NUEVOS), c["id"])

    def test_ningun_veredicto_ignorado(self):
        for f in self.res["correos"]:
            self.assertEqual(f["base"]["ignorados"], [], f["id"])
            self.assertEqual(f["ensayo"]["ignorados"], [], f["id"])

    def test_resumen_fijado(self):
        self.assertEqual(self.res["resumen"], {
            "total": 8, "cambian_tier": 1, "suben": 5, "bajan": 0, "iguales": 3})
        deltas = {f["id"]: f["delta"] for f in self.res["correos"]}
        self.assertEqual(deltas["g7_4_grave_sin_pruebas"], 6)
        self.assertEqual(deltas["g7_5_copia"], 0)
        self.assertEqual(deltas["extra_8_falso_dilema"], 0)

    def test_la_tabla_del_informe_es_la_del_script(self):
        with open(RUTA_DOC, encoding="utf-8") as f:
            doc = f.read()
        self.assertIn(self.cmp.a_markdown(self.res), doc)


if __name__ == "__main__":
    unittest.main()
