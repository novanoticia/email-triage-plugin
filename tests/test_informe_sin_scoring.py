"""informe y modo_scoring (v3.21.24): una sesión sin script no se esconde.

Prueba real con Sonnet (2026-10-20): clasificó 18 correos «por criterio
propio», sin el scoring determinista, y solo lo dijo en un párrafo. Ahora
el informe cuenta las unidades sin score numérico o sin
`modo_scoring: determinista` y lo avisa arriba. Sin red; tempfiles.
"""
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


def _u(n, score=3, **extra):
    u = {"n": n, "tier": "REVIEW", "score": score, "asunto": "Asunto %d" % n,
         "remitente": "a@x.com", "fecha": "20/10", "mids": ["<m%d>" % n],
         "accion": "propuesto"}
    u.update(extra)
    return u


class TestInformeSinScoring(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.d.name
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))

    def _informe(self, unidades, **datos):
        r = th.cmd_informe(dict({"session_id": "20261020-120000",
                                 "modo": "simulacion",
                                 "unidades": unidades}, **datos))
        self.assertTrue(r["ok"], r)
        with open(r["ruta"], encoding="utf-8") as fh:
            return r, fh.read()

    def test_sesion_determinista_no_avisa(self):
        r, md = self._informe([_u(1), _u(2)], modo_scoring="determinista")
        self.assertEqual(r["sin_scoring_determinista"], 0)
        self.assertNotIn("Sin scoring determinista", md)

    def test_el_caso_sonnet_sin_scores(self):
        # 18 correos, ninguno con score, y sin declarar nada.
        r, md = self._informe([_u(i, score=None) for i in range(1, 19)])
        self.assertEqual(r["sin_scoring_determinista"], 18)
        self.assertIn("Sin scoring determinista: 18 de 18 unidades", md)
        # El aviso va antes de cualquier tabla.
        self.assertLess(md.index("Sin scoring"), md.index("## "))

    def test_declarar_determinista_sin_score_no_basta(self):
        r, _ = self._informe([_u(1, score=None)], modo_scoring="determinista")
        self.assertEqual(r["sin_scoring_determinista"], 1)

    def test_score_sin_declarar_tampoco_basta(self):
        r, _ = self._informe([_u(1)])
        self.assertEqual(r["sin_scoring_determinista"], 1)

    def test_la_unidad_manda_sobre_la_sesion(self):
        r, md = self._informe([_u(1), _u(2, modo_scoring="mental")],
                              modo_scoring="determinista")
        self.assertEqual(r["sin_scoring_determinista"], 1)
        self.assertIn("(#2)", md)

    def test_score_booleano_no_es_numerico(self):
        r, _ = self._informe([_u(1, score=True)], modo_scoring="determinista")
        self.assertEqual(r["sin_scoring_determinista"], 1)


if __name__ == "__main__":
    unittest.main()
