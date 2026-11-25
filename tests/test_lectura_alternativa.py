"""Lectura alternativa (v3.28.13, P2 de ICD 203: análisis de alternativas).

ROADMAP, tabla P2: «Para tiers altos, una línea de "lectura alternativa"
cuando exista otra interpretación plausible». Diseño confirmado por el
mantenedor (2026-11-25): ajuste propio `scoring.lectura_alternativa`,
apagado por defecto (no reutiliza `contrato_p2`, para no cambiar a quien ya
lo tiene activo); «tier alto» = REPLY_NEEDED y REVIEW; la frase la escribe
el modelo (juicio) y `informe` solo la pinta escapada y avisa de las que
falten (mecánico). No cambia score ni tier y no frena nada. Sin red.
"""
import os
import tempfile
import unittest

from tests import DIR_SCRIPTS  # noqa: F401  (pone scripts/ en sys.path)
import triage_helpers as th

SID = "sim-20261125-0900"


def _hay_yaml():
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


class _Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.d.name
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))

    def config(self, texto):
        with open(os.path.join(self.d.name, "config.yaml"), "w",
                  encoding="utf-8") as f:
            f.write(texto)

    def informe(self, unidades):
        r = th.cmd_informe({"session_id": SID, "modo": "simulacion",
                            "modo_scoring": "determinista",
                            "unidades": unidades})
        self.assertTrue(r["ok"], r)
        with open(r["ruta"], encoding="utf-8") as fh:
            return r, fh.read()


def _u(n, tier, **extra):
    return dict({"n": n, "tier": tier, "score": 5, "asunto": "Asunto %d" % n,
                 "mids": ["<m%d@example.invalid>" % n]}, **extra)


class TestSinAjuste(_Base):
    def test_sin_config_no_hay_clave_ni_aviso_pero_se_pinta(self):
        r, md = self.informe([
            _u(1, "REVIEW"),
            _u(2, "REVIEW", lectura_alternativa="Podría ser solo informativo."),
            _u(3, "REPLY_NEEDED", lectura_alternativa=False)])
        self.assertNotIn("lectura_alternativa_ausente", r)
        self.assertNotIn("Sin lectura alternativa", md)
        self.assertIn("↔ Podría ser solo informativo.", md)
        self.assertIn("↔ sin lectura alternativa plausible", md)

    @unittest.skipUnless(_hay_yaml(), "PyYAML no instalado")
    def test_false_o_no_booleano_lo_dejan_apagado(self):
        for valor in ("false", '"true"', "1", "si"):
            with self.subTest(valor=valor):
                self.config("scoring:\n  lectura_alternativa: %s\n" % valor)
                r, _ = self.informe([_u(1, "REVIEW")])
                self.assertNotIn("lectura_alternativa_ausente", r)

    def test_config_roto_no_tumba_el_informe(self):
        self.config("scoring: [esto no cierra\n")
        r, _ = self.informe([_u(1, "REVIEW")])
        self.assertNotIn("lectura_alternativa_ausente", r)


@unittest.skipUnless(_hay_yaml(), "PyYAML no instalado")
class TestConAjuste(_Base):
    def setUp(self):
        super().setUp()
        self.config("scoring:\n  lectura_alternativa: true\n")

    def test_avisa_solo_de_los_tiers_altos_sin_campo(self):
        r, md = self.informe([
            _u(1, "REVIEW"),
            _u(2, "REPLY_NEEDED"),
            _u(3, "REVIEW", lectura_alternativa="Otra lectura."),
            _u(4, "REPLY_NEEDED", lectura_alternativa=False),
            _u(5, "READING_LATER"),
            _u(6, "ARCHIVE"),
            _u(7, "REVIEW", lectura_alternativa="   "),
            _u(8, "REVIEW", lectura_alternativa=None)])
        self.assertEqual(r["lectura_alternativa_ausente"], [1, 2, 7, 8])
        self.assertIn("Sin lectura alternativa en 4 correos de tier alto", md)
        self.assertIn("#1, #2, #7, #8", md)

    def test_todos_cubiertos_lista_vacia_y_sin_aviso(self):
        r, md = self.informe([_u(1, "REVIEW", lectura_alternativa=False),
                              _u(2, "ARCHIVE")])
        self.assertEqual(r["lectura_alternativa_ausente"], [])
        self.assertNotIn("Sin lectura alternativa en", md)

    def test_no_cambia_tiers_ni_recuentos(self):
        unidades = [_u(1, "REVIEW"), _u(2, "ARCHIVE")]
        r, _ = self.informe(unidades)
        self.assertEqual(r["por_tier"]["REVIEW"], 1)
        self.assertEqual(r["por_tier"]["ARCHIVE"], 1)

    def test_el_texto_se_escapa_como_las_razones(self):
        r, md = self.informe([_u(1, "REVIEW",
                                 lectura_alternativa="<b>ojo</b> | [x](y)")])
        self.assertNotIn("<b>", md)
        self.assertIn("&lt;b&gt;ojo&lt;/b&gt;", md)
        fila = next(linea for linea in md.splitlines() if linea.startswith("| 1 |"))
        self.assertEqual(fila.count(" | "), 4)  # una celda más rompería la tabla


class TestValidarConfig(unittest.TestCase):
    @unittest.skipUnless(_hay_yaml(), "PyYAML no instalado")
    def test_aviso_si_no_es_booleano(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "config.yaml")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write('scoring:\n  lectura_alternativa: "si"\n')
            r = th.cmd_validar_config(ruta)
        self.assertTrue(any("lectura_alternativa" in a
                            for a in r.get("avisos", [])), r)

    @unittest.skipUnless(_hay_yaml(), "PyYAML no instalado")
    def test_la_plantilla_lo_trae_apagado(self):
        import yaml
        ruta = os.path.join(os.path.dirname(DIR_SCRIPTS), "config.yaml")
        with open(ruta, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.assertIs(cfg["scoring"]["lectura_alternativa"], False)


class TestDoctrina(unittest.TestCase):
    def test_skill_y_referencia_dicen_lo_mismo_que_el_script(self):
        skill_dir = os.path.dirname(DIR_SCRIPTS)
        with open(os.path.join(skill_dir, "SKILL.md"), encoding="utf-8") as f:
            skill = " ".join(f.read().split())
        with open(os.path.join(skill_dir, "references", "paso-5r-informe.md"),
                  encoding="utf-8") as f:
            ref = " ".join(f.read().split())
        for trozo in ("`scoring.lectura_alternativa: true`",
                      "`REPLY_NEEDED` o `REVIEW`", "pasa `false`",
                      "No cambia score ni tier"):
            self.assertIn(trozo, skill)
        self.assertIn("`lectura_alternativa_ausente`", ref)
        self.assertEqual(th._TIERS_LECTURA_ALTERNATIVA, ("REPLY_NEEDED", "REVIEW"))


if __name__ == "__main__":
    unittest.main()
