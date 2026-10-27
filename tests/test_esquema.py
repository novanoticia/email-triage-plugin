"""Esquema JSON portable del evaluador nativo (`esquema.py`).

Sin red ni modelos: respuestas sintéticas. Prueban el contrato mecánico entre
el esquema y `modelos.validar`, no la calidad de ningún proveedor.
"""
import json
from pathlib import Path
import unittest

from tests import DIR_SCRIPTS
import esquema as es
import triage_helpers as th

SKILL = Path(DIR_SCRIPTS).parent
REFERENCIA = SKILL / "references" / "esquema-evaluador.json"


def _cfg_plantilla():
    return th._cargar_config(str(SKILL / "config.yaml"))


def _texto_esquema(cfg):
    # Idéntico a lo que imprime `esquema.py generar` (print añade el salto).
    return json.dumps(es.generar(cfg), ensure_ascii=False, indent=2) + "\n"


class TestReferencia(unittest.TestCase):
    def test_referencia_coincide_byte_a_byte(self):
        # Patrón del gate de es.yaml: si cambia config.yaml o esquema.py,
        # regenera con `esquema.py generar --config config.yaml`.
        self.assertEqual(
            REFERENCIA.read_bytes(),
            _texto_esquema(_cfg_plantilla()).encode("utf-8"),
            "esquema-evaluador.json desactualizado: regenéralo")


if __name__ == "__main__":
    unittest.main()
