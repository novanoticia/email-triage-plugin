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


class TestIdsInternosDeMail(unittest.TestCase):
    """Prueba 4: el lote llegó a montar-mover con los `id` internos de Mail
    (enteros) en vez del Message-ID RFC. Ahora se rechaza sin generar script."""

    BASE = {"cuenta": "iCloud", "origen": "INBOX", "destino_review": "Revisar"}

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, DIR_SCRIPTS)
        import triage_helpers as th
        cls.th = th

    def _mover(self, **extra):
        d = dict(self.BASE)
        d.update(extra)
        return self.th.cmd_montar_mover(d)

    def test_lote_de_ids_numericos_se_rechaza(self):
        lote = [284731, "284732", " 284733 ", 284734.0]
        out = self._mover(mids_review=lote[:2], mids_archive=lote[2:])
        self.assertFalse(out["ok"])
        self.assertNotIn("script", out)
        self.assertIn("id interno de Mail", out["error"])
        self.assertEqual(len(out["ids_internos"]), 4)
        self.assertEqual(out["ids_internos"][2]["lista"], "mids_archive")

    def test_un_solo_id_interno_basta_para_rechazar(self):
        out = self._mover(mids_review=["a@x.example", "99"])
        self.assertFalse(out["ok"])
        self.assertEqual(out["ids_internos"], [
            {"lista": "mids_review", "indice": 1, "valor": "99"}])

    def test_leer_cuerpos_tambien_rechaza(self):
        out = self.th.cmd_montar_leer_cuerpos(
            {"cuenta": "iCloud", "origen": "INBOX", "mids": [1, 2]})
        self.assertFalse(out["ok"])
        self.assertNotIn("script", out)
        self.assertIn("id interno de Mail", out["error"])

    def test_sin_arroba_solo_senala(self):
        out = self._mover(mids_review=["abc.def", "ok@x.example"])
        self.assertTrue(out["ok"])
        self.assertEqual([(s["indice"], s["motivo"]) for s in out["sospechosos"]],
                         [(0, "sin @ (¿no es un Message-ID?)")])

    def test_reply_que_no_se_mueve_no_se_valida(self):
        # Coherente con el resto: la lista que no llega al script no bloquea.
        self.assertTrue(self._mover(mids_review=["a@x.example"],
                                    mids_reply_needed=[123])["ok"])

    def test_el_skill_lo_documenta(self):
        self.assertIn("nunca el `id` numérico de Mail", _leer("SKILL.md"))

    def test_mids_legitimos_no_cambian(self):
        out = self._mover(mids_review=["CAF=1234@mail.gmail.com"])
        self.assertTrue(out["ok"])
        self.assertEqual(out["sospechosos"], [])


if __name__ == "__main__":
    unittest.main()
