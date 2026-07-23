#!/usr/bin/env python3
"""Tests del contrato core↔adaptador (Fase A). Aditivos: no tocan el motor.

Cubren: NormalizedEmail, que el puerto es abstracto, que MailAppAdapter
construye scripts reales (vía los montar-* de triage_helpers) y parsea el
formato real, y que GmailAdapter cumple la interfaz. La ejecución osascript
es solo-Mac; aquí se verifica que en un entorno sin osascript degrada limpio.
"""
import unittest

import contracts
from contracts import AdaptadorCorreo, NormalizedEmail, AdaptadorNoDisponible
from adapter_mailapp import MailAppAdapter
from adapter_gmail import GmailAdapter

MUESTRA_META = (
    "TOTAL:3\n"
    "#1 ||| lunes ||| Ana <a@x.com> ||| Hola ||| <mid-1@x>\n"
    "#2 ||| martes ||| Bob ||| Re: Plan ||| <mid-2@x>\n"
    "fila-basura-sin-separadores\n"        # malformada: debe ignorarse
    "#3 ||| miércoles ||| C ||| Asunto ||| con ||| pipes ||| <mid-3@x>\n"
)


class TestNormalizedEmail(unittest.TestCase):
    def test_valido_pasa(self):
        NormalizedEmail(id="1", handle="<a@x>").validar()

    def test_id_o_handle_vacio_falla(self):
        with self.assertRaises(ValueError):
            NormalizedEmail(id="", handle="<a@x>").validar()
        with self.assertRaises(ValueError):
            NormalizedEmail(id="1", handle="  ").validar()

    def test_tri_estado_respuesta(self):
        for v in (True, False, None):
            NormalizedEmail(id="1", handle="h", respuesta_pendiente=v).validar()
        with self.assertRaises(ValueError):
            NormalizedEmail(id="1", handle="h",
                            respuesta_pendiente="quizas").validar()

    def test_round_trip(self):
        e = NormalizedEmail(id="1", handle="<a@x>", asunto="Hola",
                            respuesta_pendiente=True, adapter_private={"labels": ["X"]})
        self.assertEqual(NormalizedEmail.from_dict(e.to_dict()), e)


class TestPuertoAbstracto(unittest.TestCase):
    def test_no_instanciable(self):
        with self.assertRaises(TypeError):
            AdaptadorCorreo()  # ABC con abstractos: no instanciable

    def test_ambos_backends_cumplen_el_puerto(self):
        # La prueba de que la frontera es dual: dos plataformas, un contrato.
        self.assertTrue(issubclass(MailAppAdapter, AdaptadorCorreo))
        self.assertTrue(issubclass(GmailAdapter, AdaptadorCorreo))


class TestMailAppConstruccion(unittest.TestCase):
    def setUp(self):
        self.ad = MailAppAdapter(cuenta="iCloud", carpetas={
            "origen": "INBOX", "review": "Revisar",
            "archive": "", "reply_needed": "Pendiente"})

    def test_leer_bandeja_construye_script(self):
        s = self.ad.construir_script_leer_bandeja(limite=10, ventana_horas=48)
        self.assertIn('tell application "Mail"', s)
        self.assertIn("TOTAL:", s)

    def test_mover_construye_con_destinos_de_config(self):
        s = self.ad.construir_script_mover(
            {"review": ["<m1@x>"], "archive": ["<m2@x>"]})
        self.assertIn('tell application "Mail"', s)

    def test_estado_hilo_requiere_fecha_corte(self):
        # fecha_corte es obligatorio en Mail.app (deriva del hilo).
        self.assertIn("Mail", self.ad.construir_script_estado_hilo(
            "Re: Plan|ana@x", fecha_corte="2026-07-20"))
        with self.assertRaises(ValueError):
            self.ad.construir_script_estado_hilo("Re: Plan|ana@x")

    def test_mover_rechaza_tier_desconocido(self):
        r = self.ad.mover({"inexistente": ["<m@x>"]})
        self.assertFalse(r["ok"])

    def test_mover_rechaza_reading_later_en_mailapp(self):
        # tier canónico pero SIN carpeta en Mail.app: error claro, no no-op.
        r = self.ad.mover({"reading_later": ["<m@x>"]})
        self.assertFalse(r["ok"])
        self.assertIn("reading_later", r["error"])
        self.assertEqual(self.ad.tiers_soportados,
                         ("review", "archive", "reply_needed"))


class TestMailAppParseo(unittest.TestCase):
    def setUp(self):
        self.ad = MailAppAdapter(cuenta="iCloud")

    def test_parsea_filas_reales(self):
        c = self.ad.parsear_metadatos(MUESTRA_META)
        self.assertEqual(len(c), 3)                     # la basura se ignora
        self.assertEqual(c[0].handle, "<mid-1@x>")
        self.assertEqual(c[1].asunto, "Re: Plan")
        # asunto con pipes: el id sigue siendo el ÚLTIMO campo.
        self.assertEqual(c[2].handle, "<mid-3@x>")
        self.assertTrue(all(not e.cuerpo_leido for e in c))

    def test_centinela_sin_origen(self):
        self.assertEqual(self.ad.parsear_metadatos("NO_SOURCE"), [])
        self.assertEqual(self.ad.parsear_metadatos(""), [])

    def test_estado_hilo_tri_estado(self):
        # respuesta_pendiente: NO_RESPONDIDO => pendiente => True.
        self.assertIs(self.ad.parsear_estado_hilo("NO_RESPONDIDO 0"), True)
        self.assertIs(self.ad.parsear_estado_hilo("RESPONDIDO"), False)
        self.assertIsNone(self.ad.parsear_estado_hilo("DESCONOCIDO"))


class TestMailAppEjecucionAislada(unittest.TestCase):
    def test_sin_osascript_degrada_limpio(self):
        # En sandbox/Linux no hay osascript: debe ser error de dominio, no crash.
        ad = MailAppAdapter(cuenta="iCloud")
        import shutil
        if shutil.which("osascript") is None:
            with self.assertRaises(AdaptadorNoDisponible):
                ad.leer_bandeja()


class TestGmailStub(unittest.TestCase):
    def setUp(self):
        self.ad = GmailAdapter()

    def test_cumple_interfaz_pero_no_implementado(self):
        with self.assertRaises(NotImplementedError):
            self.ad.leer_bandeja()
        with self.assertRaises(NotImplementedError):
            self.ad.estado_hilo("k")
        with self.assertRaises(NotImplementedError):
            self.ad.mover({"review": ["x"]})
        with self.assertRaises(NotImplementedError):
            self.ad.leer_cuerpos([])


if __name__ == "__main__":
    unittest.main()
