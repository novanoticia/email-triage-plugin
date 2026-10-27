"""Reglas de hilo del 4.J calculadas por `agrupar-hilos` (v3.22.16).

Prueba real (2026-10-27): 4 avisos de noreply@statuspage.io sumaron +2 por
«profundidad» y «único participante externo», como si fueran una
conversación; en otra sesión el modelo no lo hizo. Ahora lo calcula el
script y un hilo de buzones automáticos no se premia. Sin red ni disco.
"""
import json
import unittest

import tests  # noqa: F401  (su __init__ pone scripts/ en sys.path)
import triage_helpers as th


def hilo(remitentes, asunto="Incidencia en conectores"):
    correos = [{"id": i, "remitente": r, "asunto": ("Re: " if i else "") + asunto}
               for i, r in enumerate(remitentes)]
    out = th.cmd_agrupar_hilos({"correos": correos})
    assert out["ok"], out
    return out["unidades"]


class TestExtrasHilo(unittest.TestCase):
    def test_statuspage_no_puntua(self):
        u, = hilo(["Statuspage <noreply@statuspage.io>"] * 4)
        ex = u["extras_hilo"]
        self.assertEqual(ex["puntos"], 0)
        self.assertEqual(ex["detalle"], [])
        self.assertEqual({o["regla"] for o in ex["omitidos"]},
                         {"profundidad_hilo", "unico_participante_externo"})

    def test_conversacion_humana_de_tres(self):
        u, = hilo(["Ana <ana@x.com>"] * 3)
        ex = u["extras_hilo"]
        self.assertEqual(ex["puntos"], 2)
        self.assertNotIn("omitidos", ex)

    def test_dos_humanos_solo_profundidad(self):
        u, = hilo(["Ana <ana@x.com>", "Luis <luis@x.com>", "Ana <ana@x.com>"])
        self.assertEqual(u["extras_hilo"]["detalle"],
                         [{"regla": "profundidad_hilo", "puntos": 1}])

    def test_hilo_corto_no_suma_profundidad(self):
        u, = hilo(["Ana <ana@x.com>", "Luis <luis@x.com>"])
        self.assertEqual(u["extras_hilo"], {"puntos": 0, "detalle": []})

    def test_largo_penaliza_tambien_si_es_automatico(self):
        u, = hilo(["alerts@monitor.io"] * 10)
        self.assertEqual(u["extras_hilo"]["puntos"], -1)
        u, = hilo(["Ana <ana@x.com>"] * 12)
        self.assertEqual(u["extras_hilo"]["puntos"], 1)   # +1 +1 -1

    def test_mezcla_humano_y_bot_si_puntua(self):
        u, = hilo(["noreply@x.com", "Ana <ana@x.com>", "noreply@x.com"])
        self.assertEqual(u["extras_hilo"]["puntos"], 1)

    def test_individuales_no_traen_extras(self):
        out = th.cmd_agrupar_hilos({"correos": [
            {"id": 1, "remitente": "a@x.com", "asunto": "Uno"},
            {"id": 2, "remitente": "b@y.com", "asunto": ""}]})
        self.assertTrue(all("extras_hilo" not in u for u in out["unidades"]))

    def test_detector_de_automaticos(self):
        for r in ("noreply@a.io", "No-Reply <no-reply@a.io>", "donotreply@a.io",
                  "do-not-reply@a.io", "notifications@github.com",
                  "notification+abc@x.com", "mailer-daemon@x.com",
                  "bounces@x.com", "alerts@x.com", "noreply.ventas@x.com"):
            self.assertTrue(th._es_remitente_automatico(r), r)
        for r in ("info@x.com", "news@x.com", "Ana <ana@x.com>",
                  "noreplyer@x.com", "sin-arroba", "", None, 3, ["noreply@x"]):
            self.assertFalse(th._es_remitente_automatico(r), r)

    def test_salida_serializable(self):
        u, = hilo(["noreply@x.com"] * 3)
        json.dumps(u)


if __name__ == "__main__":
    unittest.main()
