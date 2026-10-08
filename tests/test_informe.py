"""Subcomando `informe` (v3.15, PASO 5.R): informe de sesión en Markdown."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402
import triage_helpers as th  # noqa: E402

MID = "20261001105412.3.02d4fe863ce906ec@mg-d1.substack.com"


def unidad(n=1, **kw):
    u = {"n": n, "tier": "REVIEW", "score": 9, "asunto": "The Dot and the Swarm",
         "remitente": "Ethan Mollick", "fecha": "01/10", "mids": [MID],
         "razon_pos": "remitente prioritario", "razon_neg": "newsletter",
         "accion": "movido", "destino": "Urgentes Claude"}
    u.update(kw)
    return u


class _ConHome(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._prev = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.dir

    def tearDown(self):
        if self._prev is None:
            os.environ.pop(th.ENV_BASE_ESTADO, None)
        else:
            os.environ[th.ENV_BASE_ESTADO] = self._prev
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def informe(self, unidades, **kw):
        datos = {"session_id": "20261008-090000", "modo": "real", "unidades": unidades}
        datos.update(kw)
        out = th.cmd_informe(datos)
        texto = None
        if out.get("ok"):
            with open(out["ruta"], encoding="utf-8") as f:
                texto = f.read()
        return out, texto


class TestInformeContenido(_ConHome):
    def test_escribe_en_informes_con_permisos_privados(self):
        out, _ = self.informe([unidad()])
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["ruta"], os.path.join(self.dir, "informes", "20261008-090000.md"))
        self.assertEqual(stat.S_IMODE(os.stat(out["ruta"]).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(out["ruta"])).st_mode), 0o700)

    def test_enlace_message_abre_el_correo_en_mail(self):
        _, t = self.informe([unidad()])
        self.assertIn("[The Dot and the Swarm](message://%3C20261001105412.3."
                      "02d4fe863ce906ec%40mg-d1.substack.com%3E)", t)

    def test_tiers_en_orden_fijo_y_filas_por_numero(self):
        _, t = self.informe([unidad(3, tier="ARCHIVE"), unidad(2), unidad(1)])
        self.assertLess(t.index("## 🟡 REVIEW (2)"), t.index("## ⚪ ARCHIVE (1)"))
        self.assertLess(t.index("| 1 |"), t.index("| 2 |"))

    def test_simulacion_lo_dice_y_no_ofrece_deshacer(self):
        _, t = self.informe([unidad(accion="propuesto")], modo="simulacion")
        self.assertIn("🧪 Simulación: no se movió ningún correo.", t)
        self.assertNotIn("deshaz el triaje", t)

    def test_real_ofrece_deshacer(self):
        _, t = self.informe([unidad()])
        self.assertIn("«deshaz el triaje»", t)

    def test_hilo_se_indica(self):
        _, t = self.informe([unidad(mids=[MID, "otro.1@x.com", "otro.2@x.com"])])
        self.assertIn("(hilo de 3)", t)


class TestInformeTextoDeTerceros(_ConHome):
    """Asunto y remitente los escribe quien envía: cada celda debe quedar inerte."""

    def test_no_se_inyectan_enlaces_html_ni_columnas(self):
        _, t = self.informe([unidad(asunto="Gana [premio](http://evil) <img src=x> | col",
                                    remitente="x\n## Título falso")])
        fila = next(l for l in t.splitlines() if l.startswith("| 1 |"))
        self.assertNotIn("](http://evil)", fila)
        self.assertNotIn("<img", fila)
        self.assertNotIn("\n## Título falso", t)
        import re
        # 5 columnas -> 6 barras sin escapar; la «| col» del asunto va escapada.
        self.assertEqual(len(re.findall(r"(?<!\\)\|", fila)), 6, fila)

    def test_mid_sospechoso_no_genera_enlace(self):
        out, t = self.informe([unidad(mids=['a"b<>c@x'])])
        self.assertEqual(out["sin_enlace"], [1])
        self.assertNotIn("message://", t)

    def test_celdas_largas_se_truncan(self):
        _, t = self.informe([unidad(asunto="x" * 500)])
        self.assertIn("x" * 139 + "…", t)
        self.assertNotIn("x" * 141, t)


class TestInformeValidacion(_ConHome):
    def test_session_id_no_puede_escapar_de_la_carpeta(self):
        for sid in ("../fuera", "a/b", "", "x" * 65, "con espacio"):
            with self.subTest(sid=sid):
                out, _ = self.informe([unidad()], session_id=sid)
                self.assertFalse(out["ok"])
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.dir), "fuera.md")))

    def test_entradas_invalidas(self):
        casos = {"sin unidades": dict(unidades=[]),
                 "modo raro": dict(modo="otro"),
                 "n repetido": dict(unidades=[unidad(1), unidad(1)]),
                 "tier raro": dict(unidades=[unidad(tier="URGENTE")]),
                 "accion rara": dict(unidades=[unidad(accion="borrado")]),
                 "n no entero": dict(unidades=[unidad(n="1")])}
        for nombre, kw in casos.items():
            with self.subTest(caso=nombre):
                datos = {"session_id": "s1", "modo": "real", "unidades": [unidad()]}
                datos.update(kw)
                self.assertFalse(th.cmd_informe(datos)["ok"])

    def test_cli_lee_de_stdin_sin_pasar_por_la_shell(self):
        datos = {"session_id": "cli1", "unidades": [unidad(asunto="it's $(whoami) `id`")]}
        env = dict(os.environ, EMAIL_TRIAGE_HOME=self.dir)
        p = subprocess.run([sys.executable, os.path.join(DIR_SCRIPTS, "triage_helpers.py"),
                            "informe"], input=json.dumps(datos), capture_output=True,
                           text=True, env=env)
        out = json.loads(p.stdout)
        self.assertTrue(out["ok"], p.stdout + p.stderr)
        with open(out["ruta"], encoding="utf-8") as f:
            self.assertIn("it's $\\(whoami\\) \\`id\\`", f.read())

    def test_snapshot_json_sigue_igual_tras_extraer_la_escritura_atomica(self):
        ruta = os.path.join(self.dir, "snap", "c.json")
        self.assertTrue(th._escribir_snapshot_json({"a": 1}, ruta, ".t-")["ok"])
        with open(ruta, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{\n  "a": 1\n}\n')
        self.assertFalse(th._escribir_snapshot_json({"a": object()}, ruta, ".t-")["ok"])


if __name__ == "__main__":
    unittest.main()
