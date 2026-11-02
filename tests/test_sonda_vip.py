"""Tests de scripts/sonda_vip.py (fase 0 de docs/diseno-historiales.md).

Solo la parte pura: lo que toca Mail.app no se puede probar fuera de macOS.
Fijan que la sonda cuenta direcciones sin devolverlas ni imprimirlas.
"""
import io
import os
import plistlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import sonda_vip as sv  # noqa: E402

DIR_SECRETA = "persona.importante@universidad.example"


class TestPuras(unittest.TestCase):
    def test_terminos_vip_del_diccionario(self):
        xml = ('<suite name="Mail"><class name="message"/>'
               '<property name="is VIP"/><property name="VIP senders"/>'
               '<property name="subject"/></suite>')
        self.assertEqual(sv.terminos_vip(xml), ["VIP senders", "is VIP"])
        self.assertEqual(sv.terminos_vip('<suite name="Mail"/>'), [])

    def test_cuenta_sin_devolver_direcciones(self):
        obj = {"Cuentas": ["yo@icloud.example"],
               "VIPSenders": [{"Email": DIR_SECRETA}, {"Email": DIR_SECRETA.upper()},
                              {"Email": "otra@banco.example"}, {"Nombre": "Ana"}]}
        res = sv.contar_en_plist(obj)
        self.assertEqual(res, (3, 2, 1))
        self.assertNotIn(DIR_SECRETA, repr(res))

    def test_texto_que_no_es_direccion(self):
        self.assertEqual(sv.contar_en_plist({"VIP": ["hola", "a@b", "x @y.z"]}), (0, 0, 1))


class TestFicheros(unittest.TestCase):
    def test_candidatos_y_salida_sin_direcciones(self):
        with tempfile.TemporaryDirectory() as home:
            md = os.path.join(home, "Library/Mail/V10/MailData")
            os.makedirs(md)
            with open(os.path.join(md, "VIPSenders.plist"), "wb") as fh:
                plistlib.dump({"VIPs": [DIR_SECRETA]}, fh)
            # Un fichero sin «vip» en el nombre no se mira.
            with open(os.path.join(md, "Otro.plist"), "wb") as fh:
                plistlib.dump({"x": "nadie@otro.example"}, fh)
            rutas = [r for r, _ in sv.candidatos(home)]
            self.assertEqual([os.path.basename(r) for r in rutas], ["VIPSenders.plist"])

            salida = io.StringIO()
            with mock.patch.object(sv.sys, "platform", "darwin"), \
                    mock.patch.object(sv.os.path, "expanduser", return_value=home), \
                    mock.patch.object(sv, "_ejecutar", return_value=(1, "", "error (-1743)")), \
                    redirect_stdout(salida):
                self.assertEqual(sv.main(), 0)
            texto = salida.getvalue()
            self.assertIn("1 direcciones (1 bajo una clave «VIP»)", texto)
            self.assertIn("error -1743", texto)
            self.assertNotIn("universidad", texto)
            self.assertNotIn("otro.example", texto)

    def test_sin_permiso_no_dice_ninguno(self):
        """Sin Acceso total al disco, `listdir` falla: la sonda lo dice en vez
        de informar «ninguno encontrado» (revisión de Codex, PR #184)."""
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "Library/Mail/V10/MailData"))
            real = os.listdir

            def denegar(ruta):
                if ruta.endswith("Library/Mail"):
                    raise PermissionError(1, "Operation not permitted")
                return real(ruta)

            with mock.patch.object(sv.os, "listdir", side_effect=denegar):
                self.assertEqual(sv.candidatos(home),
                                 [(os.path.join(home, "Library/Mail"), sv.SIN_PERMISO)])

            def denegar_maildata(ruta):
                if ruta.endswith("MailData"):
                    raise PermissionError(1, "Operation not permitted")
                return real(ruta)

            with mock.patch.object(sv.os, "listdir", side_effect=denegar_maildata):
                self.assertEqual([m for _, m in sv.candidatos(home)], [sv.SIN_PERMISO])

    def test_sin_mail_no_hay_candidatos(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(sv.candidatos(home), [])

    def test_plist_ilegible(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "vip.plist")
            with open(ruta, "wb") as fh:
                fh.write(b"no es un plist")
            obj, motivo = sv._leer_plist(ruta)
            self.assertIsNone(obj)
            self.assertTrue(motivo)

    def test_fuera_de_macos(self):
        with mock.patch.object(sv.sys, "platform", "linux"), redirect_stdout(io.StringIO()):
            self.assertEqual(sv.main(), 2)


if __name__ == "__main__":
    unittest.main()
