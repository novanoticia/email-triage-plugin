"""S5: el extracto truncado es estable al volver a sanitizarlo (v3.22.3).

Prueba real: si el corte a max_chars caía justo tras un espacio, la marca
« [truncado]» dejaba un doble espacio; `comparar` re-sanitiza el extracto y,
al colapsar los espacios, lo daba por modificado (extracto_no_sanitizado).
"""
import os
import unittest
from unittest.mock import patch

from tests import DIR_SCRIPTS  # noqa: F401  (pone scripts/ en sys.path)
from tests.test_jev import lote
import decisions as d
import triage_helpers as th


def sanear(texto, n=1500):
    return th.cmd_sanitizar(texto, n, "Asunto", "a@example.invalid")["texto"]


class TestTruncadoIdempotente(unittest.TestCase):
    def test_sin_doble_espacio_y_estable_en_cualquier_corte(self):
        base = "palabra " * 400 + "fin\n\notro párrafo con\ttabulador " * 20
        for desplaz in range(12):
            with self.subTest(desplaz=desplaz):
                s = sanear("a" * desplaz + base)
                self.assertTrue(s.endswith(" [truncado]"))
                self.assertNotIn("  [truncado]", s)
                self.assertNotRegex(s, r"\s \[truncado\]$")
                self.assertEqual(sanear(s, 2000), s)

    def test_comparar_acepta_extracto_cortado_tras_espacio(self):
        p, cfg = lote()
        cuerpo = "aaaa" + "palabra " * 400  # el corte en 1500 cae tras un espacio
        q = d.preparar({"perfil_minimo": p["perfil_minimo"], "emails": [
            {"id": "1", "asunto": "Taller", "remitente": "a@example.invalid", "cuerpo": cuerpo}]})
        q["emails"][0].update(control=p["emails"][0]["control"],
                              principal=p["emails"][0]["principal"])
        from tests.test_decisions import respuesta
        with patch.dict(os.environ, {"OPENAI_API_KEY": "ficticia"}):
            r = d.comparar(q, cfg, {"activo": True, "acepta_envio_datos": True}, respuesta)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["resultados"][0]["motivo"], "solo_comparacion")


if __name__ == "__main__":
    unittest.main()
