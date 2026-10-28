"""El config de Jev/Decisions de la base de estado manda (v3.22.23).

Prueba real 2026-10-28: el modelo pasó a `jev.py` copias temporales de la
capa (`--config-jev tmp/...`): una con `modo: hibrido` cuando la del usuario
decía `comparar`, otra sin una clave que el script instalado rechazaba.
CLI real, sin red (sin clave: 0 llamadas) y con la base en un temporal.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.test_jev import SKILL, lote

ACTIVA = "activo: true\nacepta_envio_datos: true\n"


class _Base(unittest.TestCase):
    script, opcion, fichero, clave = "jev.py", "--config-jev", "config-jev.yaml", "TYPESAFE_API_KEY"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.canonica = self.base / self.fichero
        self.copia = self.base / "tmp" / ("sesion-" + self.fichero)
        self.copia.parent.mkdir()
        self.p, _ = lote()

    def correr(self, ruta, cmd="comparar"):
        env = {k: v for k, v in os.environ.items() if k != self.clave}
        env["EMAIL_TRIAGE_HOME"] = str(self.base)
        p = self.p
        if cmd == "evaluar":
            p = json.loads(json.dumps(self.p))
            for e in p["emails"]:
                del e["principal"]
                e["contexto_suficiente"] = True
        r = subprocess.run([sys.executable, str(SKILL / "scripts" / self.script), cmd,
                            "--config", str(SKILL / "config.yaml"), self.opcion, str(ruta)],
                           input=json.dumps(p), text=True, capture_output=True, env=env)
        out = json.loads(r.stdout)
        self.assertNotIn(str(self.base), r.stdout + r.stderr)  # sin rutas
        self.assertFalse(out["permitir_movimientos"])
        return out

    def rechazo(self, ruta, motivo, cmd="comparar"):
        out = self.correr(ruta, cmd)
        self.assertFalse(out["ok"])
        self.assertEqual(out["motivo"], motivo)
        self.assertTrue(out["usar_principal"])


class TestJev(_Base):
    def test_la_canonica_funciona_como_siempre(self):
        self.canonica.write_text(ACTIVA)
        out = self.correr(self.canonica)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["llamadas"], 0)

    def test_copia_identica_se_acepta(self):
        self.canonica.write_text(ACTIVA)
        self.copia.write_text(ACTIVA)
        self.assertTrue(self.correr(self.copia)["ok"])

    def test_copia_que_cambia_el_modo_se_rechaza(self):
        # El caso real: la capa del usuario dice comparar.
        self.canonica.write_text(ACTIVA + "modo: comparar\n")
        self.copia.write_text(ACTIVA + "modo: hibrido\n")
        self.rechazo(self.copia, "config_no_coincide_con_base", cmd="evaluar")

    def test_copia_activa_sin_canonica_se_rechaza(self):
        self.copia.write_text(ACTIVA)
        self.rechazo(self.copia, "config_fuera_de_base")

    def test_copia_que_esquiva_una_canonica_invalida_se_rechaza(self):
        # El otro caso real: una clave que el script no conoce.
        self.canonica.write_text(ACTIVA + "clave_futura: 1\n")
        self.copia.write_text(ACTIVA)
        self.rechazo(self.copia, "config_base_invalida")

    def test_copia_inactiva_o_ausente_no_autoriza_y_se_acepta(self):
        self.copia.write_text("activo: false\n")
        for ruta in (self.copia, self.base / "no-existe.yaml"):
            out = self.correr(ruta)
            self.assertTrue(out["ok"])
            self.assertEqual(out["motivo"], "desactivado")

    def test_copia_mas_permisiva_se_rechaza_y_mas_estricta_no(self):
        base = {"activo": True, "acepta_envio_datos": True, "max_llamadas": 5,
                "confianza_minima": 0.8, "tolerancia_dudas": 1}
        self.canonica.write_text(yaml.safe_dump(base))
        for cambio in ({"max_llamadas": 6}, {"confianza_minima": 0.5},
                       {"tolerancia_dudas": 2}, {"acepta_envio_datos": False},
                       {"modelo": "jev-preview"}):
            with self.subTest(cambio=cambio):
                self.copia.write_text(yaml.safe_dump(dict(base, **cambio)))
                self.rechazo(self.copia, "config_no_coincide_con_base")
        estricta = dict(base, max_llamadas=2, confianza_minima=0.9, tolerancia_dudas=0)
        self.copia.write_text(yaml.safe_dump(estricta))
        self.assertTrue(self.correr(self.copia)["ok"])


class TestDecisions(_Base):
    script, opcion = "decisions.py", "--config-decisions"
    fichero, clave = "config-decisions.yaml", "OPENAI_API_KEY"

    def test_mismo_freno_en_decisions(self):
        self.canonica.write_text(ACTIVA + "modo: comparar\n")
        self.copia.write_text(ACTIVA + "modo: hibrido\n")
        self.rechazo(self.copia, "config_no_coincide_con_base", cmd="evaluar")
        self.copia.write_text(ACTIVA + "modo: comparar\n")
        self.assertTrue(self.correr(self.copia)["ok"])


if __name__ == "__main__":
    unittest.main()
