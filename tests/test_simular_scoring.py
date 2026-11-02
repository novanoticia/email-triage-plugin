"""`scripts/simular_scoring.py`: guardar veredictos y volver a puntuarlos.

Sin red y sin el proveedor: las filas son sintéticas, con los veredictos del
correo 88 de la medición 24 (boletín con B que cae a ARCHIVE con −4).
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(_RAIZ, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(_RAIZ, "scripts"))

from tests import DIR_SCRIPTS  # noqa: E402,F401  (pone la skill en sys.path)
import simular_scoring as ss  # noqa: E402
import yaml  # noqa: E402

NO_PUNTUA = ("eje", "activo", "core", "weight", "question")


def _cfg():
    with open(ss.CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _veredictos_88(cfg):
    """Un veredicto por criterio activo: el que da 0 puntos y, encima, los
    que puntuaron distinto de 0 en el correo 88 de la medición 24."""
    vs = {}
    for nombre, c in cfg["criterios_epistemicos"].items():
        if c.get("activo"):
            cero = [o for o, v in c.items() if o not in NO_PUNTUA and v == 0
                    and not isinstance(v, bool)]
            if cero:
                vs[nombre] = cero[0]
    vs.update(cambia_algo_concreto="no", cambio_predicciones="no", retorno_atencional="bajo",
              relevancia_longitudinal="quiza", abre_opciones="si", hug_the_query="directo",
              sorpresa_bayesiana="baja", forward_backward_flow="backward",
              densidad_informativa="baja", argument_screens_off_authority="argumento_fuerte",
              entangled_truths="alto")
    return vs


def _fila(cfg, ident="88", tier="ARCHIVE", score=-4, controles="B"):
    carga = {"hard_rules": ["sender_bulk_penalizacion"] if "B" in controles else [],
             "extra_points": 0, "forzar_reply_needed": "F" in controles,
             "tier_maximo": None, "remitente_en_historial": False,
             "id": ident, "verdicts": _veredictos_88(cfg)}
    return {"id": ident, "esperado": "READING_LATER", "controles": controles,
            "payload": carga, "tier": tier, "score": score}


class TestSimular(unittest.TestCase):
    def setUp(self):
        self.cfg = _cfg()

    def test_config_actual_reproduce_la_medicion(self):
        fila = _fila(self.cfg)
        self.assertEqual(ss.puntuar([fila], self.cfg), {"88": ("ARCHIVE", -4)})
        lineas = []
        ss.informe([fila], self.cfg, [], salida=lineas.append)
        self.assertFalse(any("AVISO" in x for x in lineas))

    def test_avisa_si_el_config_ya_no_da_el_tier_guardado(self):
        lineas = []
        ss.informe([_fila(self.cfg, tier="REVIEW")], self.cfg, [], salida=lineas.append)
        self.assertTrue(any(x.startswith("AVISO") and "88" in x for x in lineas))

    def test_opcion_2b_rescata_el_88(self):
        """La cuenta de la medición 24: sin el recorte, +1 y +3 pasan a
        calidad_epistemica y el 88 llega a 0 (READING_LATER)."""
        variante = dict(ss.VARIANTES)[
            "opción 2b: relevancia_longitudinal y abre_opciones a calidad_epistemica"]
        puntos = ss.puntuar([_fila(self.cfg)], ss.aplicar(self.cfg, variante))
        self.assertEqual(puntos["88"], ("READING_LATER", 0))
        lineas = []
        ss.informe([_fila(self.cfg)], self.cfg, [("2b", variante)], salida=lineas.append)
        self.assertTrue(any("[88]" in x and "✓" in x for x in lineas))

    def test_aplicar_no_toca_el_original_y_rechaza_erratas(self):
        cambiado = ss.aplicar(self.cfg, {"eje": {"abre_opciones": "calidad_epistemica"},
                                         "rango": {"valor_decisional": [-5, 10]}})
        self.assertEqual(cambiado["criterios_epistemicos"]["abre_opciones"]["eje"],
                         "calidad_epistemica")
        self.assertEqual(self.cfg["criterios_epistemicos"]["abre_opciones"]["eje"],
                         "valor_decisional")
        self.assertEqual(self.cfg["scoring"]["ejes"]["valor_decisional"], [0, 10])
        for mala in ({"eje": {"abre_opcion": "calidad_epistemica"}},
                     {"eje": {"abre_opciones": "calidad"}},
                     {"rango": {"valor": [0, 1]}}):
            with self.assertRaises(ValueError):
                ss.aplicar(self.cfg, mala)

    def test_main_con_errata_sale_sin_simular(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "v.json")
            with open(ruta, "w", encoding="utf-8") as fh:
                json.dump({"formato": ss.FORMATO, "pasadas": [[_fila(self.cfg)]]}, fh)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(ss.main([ruta, "--eje", "abre_opcion=calidad_epistemica"]), 2)
                self.assertEqual(ss.main([ruta, "--pasada", "3"]), 2)


class TestGuardar(unittest.TestCase):
    def test_guarda_solo_filas_con_veredictos_y_sin_texto(self):
        cfg = _cfg()
        carga = _fila(cfg)["payload"]
        rep = [[{"resultados": [
            {"id": "88", "propuesta": {"tier": "ARCHIVE", "score": -4}, "payload_scoring": carga,
             "evaluacion_gemini": {"eco": {"inicio": "texto del correo"}}},
            {"id": "44", "motivo": "eco_distinto"}]}]]
        esperados = [("ARCHIVE", "")] * 87 + [("READING_LATER", "B")]
        pasadas = ss.filas_guardables(rep, esperados)
        self.assertEqual([f["id"] for f in pasadas[0]], ["88"])
        self.assertEqual(set(pasadas[0][0]), {"id", "esperado", "controles", "payload",
                                              "tier", "score"})
        self.assertNotIn("texto del correo", json.dumps(pasadas))
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "v.json")
            self.assertEqual(ss.guardar(ruta, "gemini", rep, esperados), 1)
            datos = ss.cargar(ruta)
            self.assertEqual(datos["proveedor"], "gemini")
            self.assertEqual(ss.puntuar(datos["pasadas"][0], cfg), {"88": ("ARCHIVE", -4)})

    def test_cargar_rechaza_otro_formato(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "v.json")
            with open(ruta, "w", encoding="utf-8") as fh:
                json.dump({"pasadas": []}, fh)
            with self.assertRaises(ValueError):
                ss.cargar(ruta)


if __name__ == "__main__":
    unittest.main()
