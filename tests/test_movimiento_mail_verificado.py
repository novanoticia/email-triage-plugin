"""Contrato de identidad y recibos de Mail.app, sin acceder al buzón."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests import DIR_SCRIPTS

sys.path.insert(0, DIR_SCRIPTS)
import triage_helpers as th  # noqa: E402


class TestMovimientoMailVerificado(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ruta = str(Path(temp.name) / "session_log.jsonl")
        self.sid = "20261122-101500"
        self.cuenta = "cuenta-de-prueba"
        self.datos = {"cuenta": "Trabajo", "origen": "Entrada",
                      "destino_review": "Revisión", "mids_review": ["a@example.invalid"],
                      "instancias_mail": {"a@example.invalid": 125},
                      "mail_account_id": self.cuenta}
        self.recibo = {
            "lote_id": "a" * 32, "mail_account_id": self.cuenta,
            "resultados": [{"message_id": "a@example.invalid", "mail_id": 125,
                            "from_folder": "Entrada", "to_folder": "Revisión",
                            "estado": "confirmado"}],
        }

    def registrar(self):
        intento = {k: v for k, v in self.recibo["resultados"][0].items()
                   if k != "estado"}
        return th.cmd_registrar(self.ruta, dict(
            intento, session_id=self.sid, lote_id=self.recibo["lote_id"],
            mail_account_id=self.cuenta, tier="REVIEW", score=6,
            modo_scoring="determinista", status="pending"))

    def cerrar(self):
        return th.cmd_cerrar_lote(self.ruta, {"session_id": self.sid,
                                              "salida": json.dumps(self.recibo)})

    def test_script_comprueba_identidad_antes_y_despues(self):
        r = th.cmd_montar_mover(self.datos)
        self.assertTrue(r["ok"])
        script = r["script"]
        self.assertIn(r["lote_id"], script)
        self.assertIn('set instanciastoReview to {125}', script)
        self.assertLess(script.index("if (count of hits) is 1"),
                        script.index("idCandidato is idRevisado"))
        self.assertLess(script.index("idCandidato is idRevisado"),
                        script.index("move candidato to revBox"))
        self.assertLess(script.index("move candidato to revBox"),
                        script.index("if (count of restantes) is 0 and (count of llegados) is 1"))
        self.assertLess(script.index("if (count of restantes) is 0"),
                        script.index("set okRev to okRev + 1"))
        self.assertIn('set identificadorCuenta to "cuenta-de-prueba"', script)
        self.assertIn('accounts whose id is identificadorCuenta', script)

    def test_simulacion_y_lote_sin_identidad_carecen_de_script(self):
        for datos in (dict(self.datos, simulacion=True),
                      dict(self.datos, instancias_mail={}),
                      dict(self.datos, mail_account_id=None)):
            r = th.cmd_montar_mover(datos)
            self.assertFalse(r["ok"])
            self.assertNotIn("script", r)

    def test_cli_exige_identidades_de_la_captura(self):
        datos = {k: v for k, v in self.datos.items() if k != "instancias_mail"}
        for entrada in (datos, dict(datos, instancias_mail=None)):
            r = subprocess.run(
                [sys.executable, str(Path(DIR_SCRIPTS) / "triage_helpers.py"), "montar-mover"],
                input=json.dumps(entrada), capture_output=True, text=True, check=True,
            )
            salida = json.loads(r.stdout)
            self.assertFalse(salida["ok"])
            self.assertNotIn("script", salida)

    def test_cierre_concurrente_se_guarda_una_sola_vez(self):
        self.assertTrue(self.registrar()["ok"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            respuestas = list(pool.map(lambda _: self.cerrar(), range(2)))
        self.assertTrue(all(r["ok"] and r["n_ok"] == 1 for r in respuestas), respuestas)
        self.assertEqual(sum(r["bytes"] > 0 for r in respuestas), 1)
        self.assertEqual(len(Path(self.ruta).read_text().splitlines()), 2)
        out = th.cmd_estado_log(self.ruta, self.sid)
        self.assertTrue(out["ok"])
        correo, = out["correos"]
        self.assertTrue(correo["deshacible"])
        self.assertEqual(correo["mail_id"], 125)
        self.assertEqual(correo["mail_account_id"], self.cuenta)

    def test_no_verificado_queda_fuera_de_deshacer(self):
        self.assertTrue(self.registrar()["ok"])
        self.recibo["resultados"][0]["estado"] = "no_verificado"
        r = self.cerrar()
        self.assertTrue(r["ok"])
        self.assertEqual(r["n_ok"], 0)
        correo, = th.cmd_estado_log(self.ruta, self.sid)["correos"]
        self.assertEqual(correo["estado"], "no_verificado")
        self.assertFalse(correo["deshacible"])
        self.assertEqual(th.cmd_estado_log(self.ruta)["sesiones_por_revisar"][0]["session_id"],
                         self.sid)

    def test_cierre_exige_la_identidad_registrada(self):
        self.assertTrue(self.registrar()["ok"])
        self.recibo["resultados"][0]["mail_id"] = 126
        self.assertFalse(self.cerrar()["ok"])
        self.assertEqual(len(Path(self.ruta).read_text().splitlines()), 1)

    def test_deshacer_coteja_recibo_de_los_buzones_invertidos(self):
        self.assertTrue(self.registrar()["ok"])
        self.assertTrue(self.cerrar()["ok"])
        mid = "a@example.invalid"
        datos = {"session_id": self.sid, "revertidos": [mid]}
        self.assertFalse(th.cmd_cerrar_deshacer(self.ruta, datos)["ok"])
        inverso = dict(self.recibo, lote_id="b" * 32, resultados=[
            dict(self.recibo["resultados"][0], from_folder="Revisión", to_folder="Entrada")
        ])
        resultado = th.cmd_cerrar_deshacer(self.ruta, dict(datos, recibos_mail=[inverso]))
        self.assertTrue(resultado["ok"], resultado)
        self.assertEqual(resultado["n_revertidos"], 1)

    def test_correos_de_mailapp_se_presentan_individualmente(self):
        correos = [{"id": 1, "asunto": "Reunión", "remitente": "a@example.invalid"},
                   {"id": 2, "asunto": "Re: Reunión", "remitente": "b@example.invalid"}]
        r = th.cmd_agrupar_hilos({"correos": correos, "solo_individuales": True})
        self.assertEqual([u["miembros"] for u in r["unidades"]], [[correos[0]], [correos[1]]])
        grupo, = th.cmd_agrupar_hilos({"correos": correos})["unidades"]
        self.assertEqual(grupo["relacion_hilo"], "heuristica")
