"""La frontera de lectura usa solo correo ficticio y subprocesos simulados."""

import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import leer_mailapp as lector


class CapturaMailApp(unittest.TestCase):
    def setUp(self):
        self.peticion = {"cuenta": "Cuenta de prueba", "origen": "Entrada"}
        sustituto = patch.object(lector.subprocess, "run")
        self.osa = sustituto.start()
        self.addCleanup(sustituto.stop)

    def poner_respuestas(self, *respuestas):
        self.osa.side_effect = [
            subprocess.CompletedProcess(["osascript"], 0, json.dumps(r).encode())
            for r in respuestas
        ]

    def fila(self, mail_id, mid, asunto, acceso="metadatos", cuerpo=""):
        return [
            mail_id, mid, "María <maria@example.invalid>",
            asunto, "domingo, 22 de noviembre de 2026", acceso, cuerpo,
        ]

    def cuerpo(self, *identidades, **opciones):
        return {
            **self.peticion,
            "operacion": "cuerpos",
            "mail_account_id": "cuenta-simulada",
            "correos": [
                {"mail_id": mail_id, "message_id": mid} for mail_id, mid in identidades
            ],
            **opciones,
        }

    def test_stdout_del_cli_solamente_incluye_resultado_saneado(self):
        fila = self.fila(
            31, "<m31@example.invalid>", "Factura   de noviembre", "cuerpo",
            "<p>Este texto es parte de una factura de muestra.</p>",
        )
        self.poner_respuestas(["ok", "cuenta-simulada", 1, [fila]])
        peticion = self.cuerpo((31, "<m31@example.invalid>"))
        stdout = io.StringIO()
        with patch.object(lector.sys, "stdin", io.StringIO(json.dumps(peticion))):
            with redirect_stdout(stdout):
                self.assertEqual(lector.main(), 0)
        respuesta = json.loads(stdout.getvalue())
        correo, = respuesta["correos"]
        self.assertEqual(correo["texto"], "Este texto es parte de una factura de muestra.")
        self.assertEqual(correo["asunto"], "Factura de noviembre")
        self.assertEqual(correo["mail_id"], 31)
        self.assertEqual(correo["message_id"], "<m31@example.invalid>")
        self.assertNotIn("<p>", stdout.getvalue())
        args, kwargs = self.osa.call_args
        self.assertEqual(args[0][-1], "31")
        self.assertNotIn("<m31@example.invalid>", args[0])
        self.assertEqual(kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        self.assertNotIn("shell", kwargs)

    def test_metadatos_pasan_por_s0_antes_de_salir(self):
        fila = self.fila(42, "m42@example.invalid", "Asunto de la prueba")
        self.poner_respuestas(["ok", "cuenta-simulada", 3, [fila]])
        with patch.object(lector.th, "_detectar_s0", side_effect=lambda texto: (
            ["deteccion_de_prueba"] if texto == fila[3] else []
        )):
            resultado = lector.leer({**self.peticion, "limite": 1, "ventana_horas": 72})
        correo, = resultado["correos"]
        self.assertTrue(correo["injection_asunto"])
        self.assertEqual(correo["asunto"], "")
        self.assertEqual(correo["asunto_evaluable"], "")
        self.assertNotIn(fila[3], json.dumps(resultado))
        self.assertEqual(self.osa.call_args.args[0][-2:], ["1", "72"])

    def test_respuestas_fuera_de_orden_se_asocian_por_identidad(self):
        primero = self.fila(91, "m91@example.invalid", "Primero", "cuerpo",
                            "Descripción de ejemplo del correo número noventa y uno.")
        segundo = self.fila(40, "m40@example.invalid", "Segundo", "sin_cuerpo")
        self.poner_respuestas(["ok", "cuenta-simulada", 2, [segundo, primero]])
        peticion = self.cuerpo((91, "m91@example.invalid"), (40, "m40@example.invalid"))
        resultado = lector.leer(peticion)
        self.assertEqual([c["mail_id"] for c in resultado["correos"]], [91, 40])
        self.assertEqual(resultado["correos"][0]["texto"], primero[-1])
        self.assertEqual(resultado["correos"][1]["etiqueta"], "[solo metadatos]")
        self.assertFalse(resultado["correos"][1]["cuerpo_leido"])

    def test_reintento_y_sublote_no_reutilizan_resultado_de_otra_identidad(self):
        filas = [
            self.fila(11, "m11@example.invalid", "Primero", "cuerpo",
                      "Descripción del correo número once."),
            self.fila(23, "m23@example.invalid", "Segundo", "cuerpo",
                      "Descripción del correo número veintitrés."),
            self.fila(23, "M23@example.invalid", "Buzón actualizado", "cuerpo",
                      "Descripción del mensaje que llegó después."),
        ]
        self.poner_respuestas(*(
            ["ok", "cuenta-simulada", 1, [fila]] for fila in filas
        ))
        peticion = self.cuerpo((11, "m11@example.invalid"),
                               (23, "m23@example.invalid"), sublote=1)
        primera = lector.leer(peticion)
        self.assertEqual([fila["texto"] for fila in primera["correos"]],
                         [filas[0][-1], filas[1][-1]])
        segunda = lector.leer(self.cuerpo((23, "m23@example.invalid")))
        self.assertEqual(segunda["correos"], [])
        self.assertEqual(segunda["mail_ids_no_disponibles"], [23])
        self.assertEqual([c.args[0][-1] for c in self.osa.call_args_list],
                         ["11", "23", "23"])

    def test_identidad_duplicada_en_respuesta_detiene_captura(self):
        fila = self.fila(1, "m1@example.invalid", "Mensaje", "cuerpo", "Texto")
        self.poner_respuestas(["ok", "cuenta-simulada", 2, [fila, fila]])
        with self.assertRaisesRegex(lector.ErrorCaptura, "respuesta_mail_invalida"):
            lector.leer(self.cuerpo((1, "m1@example.invalid"), (2, "m2@example.invalid")))

    def test_cuenta_distinta_detiene_captura(self):
        fila = self.fila(11, "m11@example.invalid", "Mensaje", "cuerpo", "Texto")
        self.poner_respuestas(["ok", "otra-cuenta", 1, [fila]])
        with self.assertRaisesRegex(lector.ErrorCaptura, "cuenta_cambiada"):
            lector.leer(self.cuerpo((11, "m11@example.invalid")))

    def test_id_rfc_no_compatible_queda_fuera_de_la_salida_y_de_cuerpos(self):
        fila = self.fila(17, "identidad no disponible", "Ejemplo")
        self.poner_respuestas(["ok", "cuenta-simulada", 1, [fila]])
        resultado = lector.leer(self.peticion)
        self.assertIsNone(resultado["correos"][0]["message_id"])
        self.assertNotIn(fila[1], json.dumps(resultado))
        with self.assertRaisesRegex(lector.ErrorCaptura, "identidad_invalida"):
            lector.leer(self.cuerpo((17, fila[1])))
        self.osa.assert_called_once()

    def test_error_del_subproceso_no_incluye_su_salida(self):
        self.osa.side_effect = subprocess.TimeoutExpired(
            ["osascript"], 180, output=b"salida parcial simulada"
        )
        stdout = io.StringIO()
        with patch.object(lector.sys, "stdin", io.StringIO(json.dumps(self.peticion))):
            with redirect_stdout(stdout):
                self.assertEqual(lector.main(), 1)
        self.assertEqual(json.loads(stdout.getvalue()),
                         {"ok": False, "error": "tiempo_agotado"})


class NombresConTilde(unittest.TestCase):
    """v3.28.9 (prueba real 2026-11-23): Mail guardaba «Leer Después» en NFD
    y el config lo trae en NFC; con `isEqualToString:` a secas el lector daba
    `sin_buzon`. El AppleScript no corre fuera de macOS, así que se fija su
    texto: nombres de cuenta y buzón en NFC por los dos lados, identificadores
    sin normalizar."""

    def setUp(self):
        self.script = lector._SCRIPT.read_text(encoding="utf-8")

    def handler(self, nombre):
        inicio = self.script.index("on %s(" % nombre)
        return self.script[inicio:self.script.index("end %s" % nombre, inicio)]

    def test_premisa_nfc_y_nfd_son_el_mismo_texto_y_cadenas_distintas(self):
        import unicodedata
        nfc = unicodedata.normalize("NFC", "Leer Después")
        nfd = unicodedata.normalize("NFD", "Leer Después")
        self.assertNotEqual(nfc, nfd)
        self.assertEqual(unicodedata.normalize("NFC", nfd), nfc)

    def test_cuenta_y_buzon_se_comparan_en_forma_canonica(self):
        self.assertIn("my mismoNombre((name of unaCuenta) as text, nombreCuenta)",
                      self.script)
        self.assertIn("my mismoNombre((name of unBuzon) as text, nombreBuzon)",
                      self.script)
        self.assertNotIn("my exacto((name of", self.script)

    def test_mismo_nombre_solo_normaliza_nfc_en_los_dos_lados(self):
        cuerpo = self.handler("mismoNombre")
        self.assertEqual(cuerpo.count("precomposedStringWithCanonicalMapping()"), 2)
        self.assertIn("isEqualToString:", cuerpo)
        # Nada de comparaciones laxas: ni mayúsculas, ni NFKC, ni diacríticos.
        for laxo in ("caseInsensitive", "compare:", "Compatibility",
                     "DiacriticInsensitive", "localized"):
            self.assertNotIn(laxo, cuerpo)

    def test_identificadores_siguen_siendo_exactos(self):
        self.assertIn("my exacto(idCuenta, idCuentaEsperado)", self.script)
        self.assertIn("my exacto(inicioMid, finMid)", self.script)
        self.assertNotIn("precomposed", self.handler("exacto"))


if __name__ == "__main__":
    unittest.main()
