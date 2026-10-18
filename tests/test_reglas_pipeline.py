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
        self.th.cmd_registrar(self.ruta, {"event": "move_batch_done",
                                          "session_id": "S1", "n_ok": 2})
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


class TestCierreDeLote(unittest.TestCase):
    """Problema 4: las entradas `pending` nunca se cerraban, así que el log no
    distinguía «movido» de «lanzado y murió» ni de «nunca se lanzó»."""

    SALIDA = ("movidos_review:2/3 movidos_archive:1/1 archivo_nativo_fallido:0"
              " | fallidos_review:[c@x] fallidos_archive:[] | src_restantes:7")

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

    def _movs(self, sid, mids):
        for m in mids:
            self.assertTrue(self.th.cmd_registrar(self.ruta, {
                "session_id": sid, "message_id": m, "to_folder": "R",
                "score": 5, "status": "pending"})["ok"])

    def _verificar(self, sid, n):
        return self.th.cmd_verificar_sesion(
            {"session_id": sid, "esperados": n, "ruta": self.ruta})

    def test_parsea_la_salida_del_script_3(self):
        self.assertEqual(self.th._parsear_salida_mover(self.SALIDA),
                         {"n_ok": 3, "n_lanzados": 4, "fallidos": ["c@x"]})
        for malo in (None, "", "ok", 3, "movidos 3 de 4"):
            self.assertIsNone(self.th._parsear_salida_mover(malo))

    def test_cerrar_lote_confirma_la_sesion(self):
        self._movs("S1", ["a@x", "b@x", "c@x", "d@x"])
        out = self.th.cmd_cerrar_lote(self.ruta, {"session_id": "S1",
                                                  "salida": self.SALIDA})
        self.assertTrue(out["ok"], out)
        v = self._verificar("S1", 4)
        self.assertEqual((v["veredicto"], v["cierre"]), ("valido", "confirmado"))
        self.assertEqual((v["n_ok"], v["fallidos"]), (3, ["c@x"]))

    def test_sin_cierre_no_es_valido(self):
        self._movs("S1", ["a@x", "b@x"])
        v = self._verificar("S1", 2)
        self.assertFalse(v["ok"])
        self.assertEqual((v["veredicto"], v["cierre"]),
                         ("sin_cerrar", "sin_cerrar"))
        self.assertIn("cerrar-lote", v["error"])

    def test_cierre_que_no_cuadra_es_descuadre(self):
        self._movs("S1", ["a@x", "b@x", "c@x"])
        self.th.cmd_cerrar_lote(self.ruta, {"session_id": "S1",
                                            "salida": self.SALIDA})
        v = self._verificar("S1", 3)
        self.assertEqual(v["veredicto"], "descuadre")

    def test_move_failed_cuenta_como_fallido(self):
        self._movs("S1", ["a@x", "b@x"])
        self.th.cmd_registrar(self.ruta, {"event": "move_failed",
                                          "session_id": "S1",
                                          "message_id": "b@x"})
        self.th.cmd_registrar(self.ruta, {"event": "move_batch_done",
                                          "session_id": "S1", "n_ok": 1})
        v = self._verificar("S1", 2)
        self.assertEqual((v["cierre"], v["fallidos"]), ("confirmado", ["b@x"]))

    def test_sesion_anterior_es_legado(self):
        self._movs("20261001-090000", ["a@x"])
        v = self._verificar("20261001-090000", 1)
        self.assertEqual((v["veredicto"], v["cierre"]), ("valido", "legado"))
        self._movs("20261018-090000", ["b@x"])
        self.assertEqual(self._verificar("20261018-090000", 1)["cierre"],
                         "sin_cerrar")

    def test_salida_ilegible_no_escribe(self):
        out = self.th.cmd_cerrar_lote(self.ruta, {"session_id": "S1",
                                                  "salida": "todo bien"})
        self.assertFalse(out["ok"])
        self.assertFalse(os.path.exists(self.ruta))

    def test_registrar_valida_el_evento(self):
        for malo in ({"n_ok": -1}, {"n_ok": "3"}, {"n_ok": True},
                     {"n_ok": 1, "fallidos": "x"}, {"n_ok": 1, "fallidos": [1]}):
            r = {"event": "move_batch_done", "session_id": "S1"}
            r.update(malo)
            self.assertFalse(self.th.cmd_registrar(self.ruta, r)["ok"], malo)
        self.assertFalse(self.th.cmd_registrar(
            self.ruta, {"event": "move_batch_done", "n_ok": 1})["ok"])

    def test_entradas_raras_no_lanzan(self):
        import json
        for d in (None, [], "x", {}, {"session_id": 3}, {"session_id": "S"},
                  {"session_id": "S", "salida": ["movidos_review:1/1"]}):
            json.dumps(self.th.cmd_cerrar_lote(self.ruta, d))

    def test_el_skill_lo_documenta(self):
        skill = _leer("SKILL.md")
        self.assertIn("cerrar-lote", skill)
        self.assertIn("`sin_cerrar`", skill)



class TestEsperaSinSleepEncadenado(unittest.TestCase):
    """v3.21.6 (prueba real 2026-10-18): la doctrina enseñaba a esperar a Mail
    con `sleep 40; head …` y Claude Code bloquea ese patrón. Ningún texto que
    lea el modelo puede volver a enseñar un `sleep` suelto: solo dentro de un
    bucle `until … do sleep` acotado."""

    def test_ningun_sleep_fuera_de_un_bucle(self):
        import glob
        import re
        raiz = os.path.join(_RAIZ, "plugins", "email-triage")
        ficheros = glob.glob(os.path.join(raiz, "skills", "email-triage", "*.md"))
        ficheros += glob.glob(os.path.join(raiz, "skills", "email-triage",
                                           "references", "*"))
        ficheros += glob.glob(os.path.join(raiz, "commands", "*.md"))
        malos = []
        for f in ficheros:
            with open(f, encoding="utf-8") as fh:
                for n, linea in enumerate(fh, 1):
                    if (re.search(r"\bsleep\s+\d", linea)
                            and not re.search(r"\buntil\b.*\bdo\s+sleep\b", linea)):
                        malos.append("%s:%d" % (os.path.basename(f), n))
        self.assertEqual(malos, [])

    def test_la_doctrina_lo_prohibe(self):
        doc = _leer("references", "paso-1-doctrina-ejecucion.md")
        self.assertIn("Nunca encadenes `sleep N; cat …`", doc)
        self.assertIn("run_in_background", doc)



class TestFrenoPlantilla(unittest.TestCase):
    """v3.21.7 (prueba real 9): un lote con veredictos asignados por remitente
    se movió como si fuera triaje. scoring marca el bloque idéntico y
    registrar se niega a contarlo como triaje."""

    V = {"cambia_algo_concreto": "no", "cambio_predicciones": "no",
         "hug_the_query": "tangencial"}

    def _lote(self, n_iguales, n_distintos=0):
        emails = [{"id": i, "verdicts": dict(self.V)} for i in range(n_iguales)]
        for j in range(n_distintos):
            v = dict(self.V)
            v["cambia_algo_concreto"] = "si" if j % 2 else "parcial"
            v["extra_%d" % j] = "no"
            emails.append({"id": 100 + j, "verdicts": v})
        return {"emails": emails}

    def _cfg(self):
        import triage_helpers as th
        return th._cargar_config(os.path.join(
            _RAIZ, "plugins", "email-triage", "skills", "email-triage",
            "config.yaml"))

    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML no instalado")
        import triage_helpers as th
        self.th = th

    def test_bloque_de_cinco_iguales_se_marca(self):
        out = self.th.cmd_scoring_dispatch(self._lote(5, 2), self._cfg(),
                                           brief=True)
        alerta = out["alerta_plantilla"]
        self.assertEqual(alerta["correos"], 5)
        self.assertEqual(alerta["grupos"][0]["ids"], [0, 1, 2, 3, 4])
        marcados = [r["id"] for r in out["resultados"] if r.get("plantilla")]
        self.assertEqual(marcados, [0, 1, 2, 3, 4])

    def test_cuatro_iguales_no_alertan(self):
        out = self.th.cmd_scoring_dispatch(self._lote(4, 3), self._cfg())
        self.assertNotIn("alerta_plantilla", out)
        self.assertFalse(any(r.get("plantilla") for r in out["resultados"]))

    def test_pocos_criterios_no_cuentan(self):
        lote = {"emails": [{"id": i, "verdicts": {"cambia_algo_concreto": "no"}}
                           for i in range(8)]}
        self.assertNotIn("alerta_plantilla",
                         self.th.cmd_scoring_dispatch(lote, self._cfg()))

    def test_items_raros_no_revientan(self):
        lote = self._lote(5)
        lote["emails"] += [None, 3, {"id": 9, "verdicts": "x"},
                           {"id": 10, "verdicts": {"a": object(), "b": 1, "c": 2}}]
        out = self.th.cmd_scoring_dispatch(lote, self._cfg())
        self.assertEqual(out["alerta_plantilla"]["correos"], 5)

    def test_registrar_rechaza_plantilla_como_triaje(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "s.jsonl")
            mov = {"event": "move", "message_id": "<a@b>", "to_folder": "X",
                   "score": -6, "plantilla": True}
            r = self.th.cmd_registrar(ruta, mov)
            self.assertIs(r["ok"], False)
            self.assertIn("regla_manual", r["remedio"])
            self.assertFalse(os.path.exists(ruta))
            mov.update(origen="regla_manual", regla="plantilla=remitente")
            self.assertIs(self.th.cmd_registrar(ruta, mov)["ok"], True)
            mov2 = dict(mov, plantilla=False, origen="triaje")
            self.assertIs(self.th.cmd_registrar(ruta, mov2)["ok"], True)

    def test_toda_negativa_de_movimiento_bloquea(self):
        # Codex P1: el SKILL decía «si registrar falla, avisa y continúa».
        casos = [{"to_folder": "X", "score": 1, "plantilla": True},
                 {"to_folder": "X"},
                 {"to_folder": "X", "origen": "raro", "score": 1},
                 {"to_folder": "X", "origen": "regla_manual"}]
        for reg in casos:
            with self.subTest(reg=reg):
                self.assertIs(self.th._valida_movimiento(reg)["bloquea_movimiento"],
                              True)
        self.assertIsNone(self.th._valida_movimiento({"to_folder": "X",
                                                      "score": 1}))

    def test_lote_delegado_tambien_frena(self):
        # Codex P1: modelos.py y jev.py puntúan correo a correo.
        import modelos
        cfg = self._cfg()
        filas = []
        for i in range(6):
            pay = {"id": i, "verdicts": dict(self.V)}
            clave = "resultado" if i % 2 else "propuesta"   # nativo / Jev
            filas.append({"id": i, "usar_principal": False, "motivo": "x",
                          "payload_scoring": pay,
                          clave: self.th.cmd_scoring_dispatch(pay, cfg)})
        filas.append({"id": 9, "usar_principal": True, "motivo": "control_invalido"})
        salida = {"ok": True, "resultados": filas}
        modelos._frenar_plantillas(salida)
        self.assertEqual(salida["alerta_plantilla"]["correos"], 6)
        self.assertTrue(all(r["usar_principal"] for r in filas))
        self.assertEqual({r["motivo"] for r in filas[:6]}, {"plantilla"})

    def test_skill_y_claude_md_lo_documentan(self):
        self.assertIn("alerta_plantilla", _leer("SKILL.md"))
        self.assertIn("bloquea_movimiento", _leer("SKILL.md"))
        with open(os.path.join(_RAIZ, "CLAUDE.md"), encoding="utf-8") as f:
            self.assertIn("plantilla", f.read())


if __name__ == "__main__":
    unittest.main()
