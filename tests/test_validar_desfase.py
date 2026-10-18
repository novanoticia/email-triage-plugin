"""validar-config (v3.21.8): avisos de config desfasado o mal puesto.

Pruebas reales 5-10 (2026-10-18): el config personal tenía 12 criterios core
frente a los 13 de la plantilla, `guardar_desglose` no surtía efecto y había
remitentes prioritarios que eran nombres. validar-config devolvía ok sin
avisar. Solo informa: nunca cambia el config. Solo stdlib + PyYAML.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from tests import DIR_SCRIPTS  # noqa: E402
import triage_helpers as th  # noqa: E402

PLANTILLA = os.path.join(os.path.dirname(DIR_SCRIPTS), "config.yaml")
SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")


class _Base(unittest.TestCase):
    def setUp(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML no instalado")
        self.yaml = yaml
        with open(PLANTILLA, encoding="utf-8") as f:
            self.texto = f.read()
        self.cfg = yaml.safe_load(self.texto)
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def _validar(self, cfg, cabecera=None, plantilla=PLANTILLA):
        ruta = os.path.join(self.dir.name, "config.yaml")
        with open(ruta, "w", encoding="utf-8") as f:
            if cabecera:
                f.write(cabecera + "\n")
            self.yaml.safe_dump(cfg, f, allow_unicode=True)
        return th.cmd_validar_config(ruta, plantilla)


class TestDesfase(_Base):
    def test_la_plantilla_contra_si_misma_no_avisa(self):
        r = th.cmd_validar_config(PLANTILLA, PLANTILLA)
        d = r["desfase"]
        self.assertEqual((d["core_faltan"], d["core_sobran"],
                          d["criterios_ausentes"], d["opciones_nuevas"]),
                         ([], [], [], []))
        self.assertEqual(d["version_config"], d["version_plantilla"])

    def test_core_de_menos_version_vieja_y_opciones_nuevas(self):
        crit = self.cfg["criterios_epistemicos"]
        quitado = sorted(n for n, c in crit.items() if c.get("core"))[0]
        crit[quitado]["core"] = False
        del self.cfg["telemetria"]["guardar_desglose"]
        r = self._validar(self.cfg, "# EMAIL TRIAGE v3.13 — Configuración")
        d = r["desfase"]
        self.assertEqual(d["core_faltan"], [quitado])
        self.assertEqual(d["core_tuyo"], d["core_plantilla"] - 1)
        self.assertEqual(d["version_config"], "3.13")
        self.assertIn("telemetria.guardar_desglose", d["opciones_nuevas"])
        texto = " ".join(r["avisos"])
        self.assertIn("v3.13", texto)
        self.assertIn(quitado, texto)

    def test_sin_plantilla_no_hay_desfase(self):
        r = self._validar(self.cfg)
        self.assertNotIn("desfase", self._validar(self.cfg, plantilla=None))
        self.assertIn("desfase", r)

    def test_plantilla_ilegible_avisa_sin_fallar(self):
        r = self._validar(self.cfg, plantilla=os.path.join(self.dir.name, "no.yaml"))
        self.assertIs(r["ok"], True)
        self.assertIsNone(r["desfase"])
        self.assertTrue(any("plantilla" in a for a in r["avisos"]))

    def test_nunca_toca_el_config(self):
        ruta = os.path.join(self.dir.name, "config.yaml")
        self._validar(self.cfg)
        with open(ruta, "rb") as f:
            antes = f.read()
        th.cmd_validar_config(ruta, PLANTILLA)
        with open(ruta, "rb") as f:
            self.assertEqual(f.read(), antes)


class TestAvisosDelUsuario(_Base):
    def test_guardar_desglose_fuera_de_telemetria(self):
        del self.cfg["telemetria"]["guardar_desglose"]
        self.cfg["filtros"]["guardar_desglose"] = True
        r = self._validar(self.cfg, plantilla=None)
        self.assertIs(r["guardar_desglose_efectivo"], False)
        self.assertTrue(any("fuera del bloque telemetria" in a and "filtros" in a
                            for a in r["avisos"]))

    def test_guardar_desglose_no_booleano(self):
        self.cfg["telemetria"]["guardar_desglose"] = "si"
        r = self._validar(self.cfg, plantilla=None)
        self.assertIs(r["guardar_desglose_efectivo"], False)
        self.assertTrue(any("true o false" in a for a in r["avisos"]))
        self.cfg["telemetria"]["guardar_desglose"] = True
        self.assertIs(self._validar(self.cfg, plantilla=None)
                      ["guardar_desglose_efectivo"], True)

    def test_remitentes_que_son_nombres(self):
        self.cfg["filtros"]["remitentes_prioritarios"] = [
            "slavoj@substack.com", "Žižek", "@cienciacognitiva.org"]
        r = self._validar(self.cfg, plantilla=None)
        self.assertEqual(r["remitentes_no_validos"], ["Žižek"])
        self.cfg["filtros"]["remitentes_ignorar"] = "spam@x.com"
        r = self._validar(self.cfg, plantilla=None)
        self.assertTrue(any("debe ser una lista" in a for a in r["avisos"]))


class TestCLI(_Base):
    def test_flag_sin_ruta_usa_la_plantilla_instalada(self):
        p = subprocess.run([sys.executable, SCRIPT, "validar-config",
                            "--config", PLANTILLA, "--plantilla"],
                           capture_output=True, text=True, timeout=60)
        r = json.loads(p.stdout)
        self.assertEqual(r["desfase"]["core_faltan"], [])
        self.assertEqual(os.path.realpath(th.RUTA_PLANTILLA),
                         os.path.realpath(PLANTILLA))

    def test_el_skill_lo_pide(self):
        with open(os.path.join(os.path.dirname(DIR_SCRIPTS), "SKILL.md"),
                  encoding="utf-8") as f:
            self.assertIn("--config ~/.email-triage/config.yaml --plantilla",
                          f.read())


if __name__ == "__main__":
    unittest.main()
