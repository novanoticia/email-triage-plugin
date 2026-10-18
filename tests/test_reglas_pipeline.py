"""Reglas del pipeline que el modelo debe respetar (problemas vistos en las
pruebas reales del mantenedor, 2026-10-17/18).

Son instrucciones del SKILL, no mecanismos: este test fija que el texto
existe y es coherente para que no desaparezca en silencio. Solo stdlib.
"""
import os
import sys
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402

SKILL_DIR = os.path.dirname(DIR_SCRIPTS)


def _leer(*partes):
    with open(os.path.join(SKILL_DIR, *partes), encoding="utf-8") as f:
        return f.read()


class TestVeredictosNoSeAjustanAlReparto(unittest.TestCase):
    """Prueba 3: el modelo «recalibró» veredictos porque 134 de 148 caían
    en REVIEW. El reparto se informa; no se corrige retocando juicios."""

    @classmethod
    def setUpClass(cls):
        cls.skill = _leer("SKILL.md")

    def test_regla_en_errores_comunes(self):
        errores = self.skill.split("## Errores comunes a evitar", 1)[1]
        self.assertIn("No ajustes veredictos para obtener un reparto", errores)
        self.assertIn("dilo en el resumen como hallazgo", errores)

    def test_regla_junto_a_la_invocacion_del_scoring(self):
        i = self.skill.index("**Cómo se invoca** (solo en modo determinista)")
        self.assertIn("Fija los veredictos de cada correo",
                      self.skill[i:i + 400])


class TestSimulacionYDesglose(unittest.TestCase):
    """v3.21.0 permitió `guardar_desglose` en simulación: las dos reglas de
    simulación deben nombrar esa excepción para no contradecirla."""

    def test_skill_y_referencia_nombran_la_excepcion(self):
        skill = _leer("SKILL.md")
        linea = next(l for l in skill.splitlines()
                     if l.startswith("- En modo simulación, NUNCA"))
        self.assertIn("guardar_desglose", linea)
        self.assertIn("guardar_desglose", _leer("references", "modo-simulacion.md"))


class TestMovimientoSinScoring(unittest.TestCase):
    """Pruebas 4 y 5: 286 y 343 correos movidos solo por remitente quedaron
    registrados como un triaje y verificar-sesion dio «valido». Ahora un
    movimiento sin `score` solo entra como regla manual explícita."""

    def setUp(self):
        import tempfile
        sys.path.insert(0, DIR_SCRIPTS)
        import triage_helpers as th
        self.th = th
        self.dir = tempfile.mkdtemp()
        self.ruta = os.path.join(self.dir, "session_log.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def _mov(self, **extra):
        r = {"session_id": "S1", "message_id": "a@x", "to_folder": "Leer"}
        r.update(extra)
        return r

    def test_triaje_con_score_se_acepta(self):
        self.assertTrue(self.th.cmd_registrar(self.ruta, self._mov(score=7))["ok"])

    def test_movimiento_sin_score_se_rechaza(self):
        for extra in ({}, {"score": None}, {"score": "7"}, {"score": True}):
            out = self.th.cmd_registrar(self.ruta, self._mov(**extra))
            self.assertFalse(out["ok"], extra)
            self.assertIn("regla_manual", out["remedio"])
        self.assertFalse(os.path.exists(self.ruta))   # no escribió nada

    def test_regla_manual_exige_regla(self):
        self.assertTrue(self.th.cmd_registrar(self.ruta, self._mov(
            origen="regla_manual", regla="remitente=x@y.example",
            tier=None, score=None))["ok"])
        self.assertFalse(self.th.cmd_registrar(
            self.ruta, self._mov(origen="regla_manual"))["ok"])

    def test_origen_desconocido_se_rechaza(self):
        self.assertFalse(self.th.cmd_registrar(
            self.ruta, self._mov(origen="intuicion", score=3))["ok"])

    def test_registros_que_no_son_movimientos_siguen_libres(self):
        for r in ({"event": "move_failed", "session_id": "S1"},
                  {"accion": "user_override", "tier_nuevo": "REVIEW"}):
            self.assertTrue(self.th.cmd_registrar(self.ruta, r)["ok"], r)

    def test_verificar_sesion_cuenta_por_origen(self):
        self.th.cmd_registrar(self.ruta, self._mov(score=3))
        self.th.cmd_registrar(self.ruta, self._mov(
            message_id="b@x", origen="regla_manual", regla="remitente=z"))
        out = self.th.cmd_verificar_sesion(
            {"session_id": "S1", "esperados": 2, "ruta": self.ruta})
        self.assertEqual(out["veredicto"], "valido")
        self.assertEqual(out["por_origen"],
                         {"triaje": 1, "regla_manual": 1, "otro": 0})

    def test_el_skill_lo_documenta(self):
        skill = _leer("SKILL.md")
        self.assertIn('"origen":"regla_manual"', skill)
        errores = skill.split("## Errores comunes a evitar", 1)[1]
        self.assertIn("es «estimado»", errores)


if __name__ == "__main__":
    unittest.main()
