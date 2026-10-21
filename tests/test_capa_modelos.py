"""capa_modelos (v3.21.20): validar-config informa de config-modelos.yaml.

Prueba real comparar (2026-10-20): con el fichero en su sitio, el modelo no
lo leyó hasta que se le pidió. Ahora lo lee `validar-config`, que el PASO 0
ya ejecuta siempre, y la salida dice el estado y el config del plan. Las
reglas son las mismas que aplica `modelos.py planificar`. Sin red; tempfiles.
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

if DIR_SCRIPTS not in sys.path:
    sys.path.insert(0, DIR_SCRIPTS)
import modelos  # noqa: E402
import triage_helpers as th  # noqa: E402

try:
    import yaml  # noqa: F401
    HAY_YAML = True
except ImportError:
    HAY_YAML = False

SCRIPT = os.path.join(DIR_SCRIPTS, "triage_helpers.py")
PLANTILLA = os.path.join(os.path.dirname(DIR_SCRIPTS), "config.yaml")


@unittest.skipUnless(HAY_YAML, "requiere PyYAML")
class TestCapaModelos(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        # La capa se lee de la base de estado, no de junto al config.
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.d.name
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))
        self.config = os.path.join(self.d.name, "config.yaml")
        with open(PLANTILLA, encoding="utf-8") as fh, \
                open(self.config, "w", encoding="utf-8") as out:
            out.write(fh.read())

    def _capa(self, texto=None):
        if texto is not None:
            with open(os.path.join(self.d.name, "config-modelos.yaml"), "w",
                      encoding="utf-8") as fh:
                fh.write(texto)
        r = th.cmd_validar_config(self.config)
        self.assertTrue(r["ok"], r)
        return r

    def test_sin_fichero_es_ausente(self):
        r = self._capa()
        self.assertEqual(r["capa_modelos"]["estado"], "ausente")
        self.assertEqual(r["capa_modelos"]["modo"], "actual")

    def test_modo_actual_es_desactivada(self):
        r = self._capa("modo: actual\nmax_llamadas: 2\n")
        self.assertEqual(r["capa_modelos"]["estado"], "desactivada")
        self.assertFalse(any("config-modelos" in a for a in r["avisos"]))

    def test_comparar_activa_con_los_valores_del_usuario(self):
        # El caso de la prueba real: 5 llamadas y lote de 10, a mano.
        r = self._capa('modo: comparar\nmodelo: ""\nmax_llamadas: 5\n'
                       'tamano_lote: 10\n')
        capa = r["capa_modelos"]
        self.assertEqual(capa["estado"], "activa")
        self.assertEqual(capa["config"], {"modo": "comparar", "modelo": "",
                                          "max_llamadas": 5,
                                          "tamano_lote": 10})
        self.assertTrue(any("modelos-nativos.md" in a for a in r["avisos"]))

    def test_activa_dice_que_delegue_sin_pedir_permiso(self):
        # v3.21.29: en dos pruebas reales la persona tuvo que pedirlo.
        capa = self._capa('modo: comparar\n')["capa_modelos"]
        self.assertEqual(capa["agente"], "email-triage:evaluador-criterios")
        self.assertIn("sin pedir permiso", capa["siguiente"])
        for texto in ("modo: actual\n", "modo: raro\n"):
            capa = self._capa(texto)["capa_modelos"]
            self.assertNotIn("agente", capa, texto)
            self.assertNotIn("siguiente", capa, texto)

    def test_invalida_se_trata_como_actual(self):
        casos = {"modo: turbo\n": "modo_no_admitido",
                 "modo: comparar\nextra: 1\n": "opcion_no_admitida",
                 "modo: comparar\nmax_llamadas: 0\n": "presupuesto_invalido",
                 "modo: hibrido\ntamano_lote: 99\n": "presupuesto_invalido",
                 "modo: comparar\nmodelo: 3\n": "modelo_invalido",
                 "modo: comparar\nmodelo: false\n": "modelo_invalido",
                 "modo: comparar\nmodelo: []\n": "modelo_invalido",
                 "- una lista\n": "config_modelos_invalida",
                 "modo: [roto\n": "yaml_roto"}
        for texto, motivo in casos.items():
            with self.subTest(texto=texto):
                r = self._capa(texto)
                capa = r["capa_modelos"]
                self.assertEqual((capa["estado"], capa["modo"],
                                  capa["motivo"]),
                                 ("invalida", "actual", motivo))
                self.assertTrue(any("no válido" in a for a in r["avisos"]))

    def test_lee_la_base_de_estado_no_la_carpeta_del_config(self):
        # Revisión Codex (PR #89): validar la plantilla del plugin no debe
        # leer la capa de la plantilla (modo actual) en vez de la del usuario.
        with open(os.path.join(self.d.name, "config-modelos.yaml"), "w",
                  encoding="utf-8") as fh:
            fh.write("modo: comparar\n")
        r = th.cmd_validar_config(PLANTILLA)
        self.assertEqual(r["capa_modelos"]["estado"], "activa")
        self.assertEqual(r["capa_modelos"]["ruta"],
                         os.path.join(self.d.name, "config-modelos.yaml"))

    def test_modelo_sin_valor_es_el_economico(self):
        capa = self._capa("modo: comparar\nmodelo:\n")["capa_modelos"]
        self.assertEqual((capa["estado"], capa["config"]["modelo"]),
                         ("activa", ""))

    def test_planificar_aplica_las_mismas_reglas(self):
        for cfg in ({"modo": "turbo"}, {"modo": "comparar", "extra": 1},
                    {"modo": "comparar", "max_llamadas": 11},
                    {"modo": "hibrido", "tamano_lote": True}, []):
            with self.subTest(cfg=cfg):
                plan = modelos.planificar({"config": cfg})
                self.assertEqual(plan["motivo"], th._motivo_capa_modelos(cfg))

    def test_cli(self):
        with open(os.path.join(self.d.name, "config-modelos.yaml"), "w",
                  encoding="utf-8") as fh:
            fh.write("modo: comparar\n")
        r = subprocess.run([sys.executable, SCRIPT, "validar-config",
                            "--config", self.config],
                           capture_output=True, text=True, timeout=30,
                           env=dict(os.environ))
        capa = json.loads(r.stdout)["capa_modelos"]
        self.assertEqual(capa["config"]["max_llamadas"], 2)   # por defecto
        self.assertEqual(capa["config"]["tamano_lote"], 25)


if __name__ == "__main__":
    unittest.main()
