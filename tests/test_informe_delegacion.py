"""El informe avisa de la delegación de modelos no hecha (v3.21.34).

Pruebas reales 2026-10-21: con `config-modelos.yaml` en `comparar`, el
modelo cerró el dry-run diciendo «tampoco ejecuté la comparación; si la
quieres, la hago aparte». `informe` lee la capa por su cuenta y, si está
activa (comparar o híbrido) y la sesión no declara `delegacion: {"hecha":
true}`, lo avisa arriba y devuelve `delegacion_pendiente`. `modo_modelos`
(el efectivo de la sesión) manda sobre el fichero. Sin red; tempfiles.
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

UNIDAD = {"n": 1, "tier": "REVIEW", "score": 5, "asunto": "A", "remitente": "a@x.com",
          "fecha": "21/10", "mids": ["<m1>"], "accion": "propuesto"}


class TestInformeComparacion(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.d.name
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))

    def _capa(self, texto):
        with open(os.path.join(self.d.name, th.NOMBRE_CAPA_MODELOS), "w",
                  encoding="utf-8") as fh:
            fh.write(texto)

    def _informe(self, **datos):
        r = th.cmd_informe(dict({"session_id": "20261021-090000",
                                 "modo": "simulacion", "modo_scoring": "determinista",
                                 "unidades": [dict(UNIDAD)]}, **datos))
        self.assertTrue(r["ok"], r)
        with open(r["ruta"], encoding="utf-8") as fh:
            return r, fh.read()

    def test_sin_capa_nada_cambia(self):
        r, md = self._informe()
        self.assertNotIn("delegacion_pendiente", r)
        self.assertNotIn("Delegación de modelos", md)

    def test_capa_desactivada_nada_cambia(self):
        self._capa("modo: actual\n")
        r, md = self._informe()
        self.assertNotIn("delegacion_pendiente", r)

    def test_el_caso_real_activa_y_no_hecha(self):
        self._capa("modo: comparar\n")
        r, md = self._informe()
        self.assertTrue(r["delegacion_pendiente"])
        self.assertIn("Delegación de modelos sin hacer", md)
        self.assertIn("`comparar`", md)
        self.assertIn("sin motivo declarado", md)
        self.assertLess(md.index("Delegación de modelos"), md.index("## "))

    def test_no_hecha_con_motivo(self):
        self._capa("modo: comparar\n")
        _, md = self._informe(delegacion={"hecha": False,
                                           "motivo": "planificar: delegar false"})
        self.assertIn("motivo: planificar: delegar false", md)

    def test_hecha_no_avisa(self):
        self._capa("modo: comparar\n")
        r, md = self._informe(delegacion={"hecha": True})
        self.assertFalse(r["delegacion_pendiente"])
        self.assertNotIn("Delegación de modelos sin hacer", md)

    def test_hecha_mal_formada_cuenta_como_no_hecha(self):
        self._capa("modo: comparar\n")
        for malo in ("si", {"hecha": "true"}, {"hecha": 1}, []):
            r, _ = self._informe(delegacion=malo)
            self.assertTrue(r["delegacion_pendiente"], malo)

    def test_el_motivo_se_neutraliza(self):
        self._capa("modo: comparar\n")
        _, md = self._informe(delegacion={"hecha": False,
                                           "motivo": "x\n## inyectado [l](http://e)"})
        self.assertNotIn("\n## inyectado", md)


    def test_hibrido_tambien_avisa_y_se_cumple_delegando(self):
        # Revisión Codex (PR #103): en híbrido se delega sin comparar.
        self._capa("modo: hibrido\n")
        r, md = self._informe()
        self.assertIn("`hibrido`", md)
        r, _ = self._informe(delegacion={"hecha": True})
        self.assertFalse(r["delegacion_pendiente"])

    def test_la_sesion_manda_sobre_el_fichero(self):
        # Revisión Codex (PR #103): pedida solo para esta sesión...
        r, md = self._informe(modo_modelos="comparar")
        self.assertTrue(r["delegacion_pendiente"])
        # ...o anulada solo para esta sesión.
        self._capa("modo: comparar\n")
        r, md = self._informe(modo_modelos="actual")
        self.assertNotIn("delegacion_pendiente", r)
        self.assertNotIn("Delegación de modelos", md)

    def test_modo_de_sesion_invalido_se_ignora(self):
        self._capa("modo: comparar\n")
        for malo in ("raro", 1, None, ["comparar"]):
            r, _ = self._informe(modo_modelos=malo)
            self.assertTrue(r["delegacion_pendiente"], malo)


if __name__ == "__main__":
    unittest.main()
