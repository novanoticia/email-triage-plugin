"""Tolerancia a dudas que no cambian el tier (v3.22.22, opt-in).

Medición real 2026-10-27 (`scripts/medir_ruido.py`, gpt-6-luna, perfil real):
15 de 30 criterios cambian entre tiradas, pero los 4 correos dan el mismo
tier en las 5. Con Jev/Decisions un solo `__incierto__` o una confianza baja
descartaba el correo entero aunque la duda no pudiera mover la decisión.
Sin red: transporte simulado; prueban el freno, no la calidad del proveedor.
"""
import os
import unittest
from unittest.mock import patch

from tests.test_jev import ACTIVO, lote, respuesta
import clasificadores as nc
import decisions as d
import jev as j

K = "cambia_algo_concreto"  # su «no» vale -5: con margen justo mueve el tier


def _con_duda(criterios, incierto=True):
    """Transporte que marca `criterios` como inciertos o de confianza baja."""
    def t(body, *_):
        r = respuesta(body)
        for k in criterios:
            a = r["answers"][k]
            if incierto:
                a.update(choice=nc.INCIERTO,
                         probabilities={o: float(o == nc.INCIERTO) for o in a["probabilities"]})
            else:
                n = len(a["probabilities"])
                a.update(probabilities={o: (0.5 if o == a["choice"] else 0.5 / (n - 1))
                                        for o in a["probabilities"]})
                a["confidence"] = (0.5 - 1 / n) / (1 - 1 / n)
        return r
    return t


class _Base(unittest.TestCase):
    modo = "comparar"

    def setUp(self):
        self.env = patch.dict(os.environ, {"TYPESAFE_API_KEY": "clave-ficticia"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.p, self.cfg = lote()
        if self.modo == "hibrido":
            for e in self.p["emails"]:
                del e["principal"]
                e["contexto_suficiente"] = True

    def capa(self, tolerancia):
        return dict(ACTIVO, modo=self.modo, tolerancia_dudas=tolerancia)

    def fijar_score(self, valor, transporte):
        """Ajusta extra_points para que la propuesta sin dudas dé `valor`."""
        e = self.p["emails"][0]
        body = {"model": j.DEFAULT["modelo"], "questions": j._preguntas(self.cfg, j._opciones(self.cfg))}
        vs = {k: a["choice"] for k, a in transporte(body)["answers"].items()
              if a["choice"] not in (nc.INCIERTO, nc.NO_APLICA)}
        e["control"]["extra_points"] += valor - j._scoring(e["id"], e["control"], vs, self.cfg)["score"]

    def correr(self, tolerancia, transporte):
        f = j.comparar if self.modo == "comparar" else j.evaluar
        return f(self.p, self.cfg, self.capa(tolerancia), transporte)["resultados"][0]


class TestComparar(_Base):
    def test_desactivada_por_defecto_el_freno_no_cambia(self):
        t = _con_duda([K])
        self.fijar_score(30, t)
        fila = j.comparar(self.p, self.cfg, ACTIVO, t)["resultados"][0]
        self.assertEqual(fila["motivo"], "jev_incierto")
        self.assertNotIn("dudas_irrelevantes", fila)
        self.assertNotIn("propuesta", fila)

    def test_duda_que_no_cambia_el_tier_se_acepta(self):
        t = _con_duda([K])
        self.fijar_score(30, t)  # lejos de cualquier umbral
        fila = self.correr(1, t)
        self.assertEqual(fila["motivo"], "solo_comparacion", fila)
        di = fila["dudas_irrelevantes"]
        self.assertEqual(di["criterios"], [K])
        self.assertEqual(di["tier"], fila["propuesta"]["tier"])
        self.assertGreater(di["combinaciones"], 1)
        self.assertLessEqual(di["score_min"], di["score_max"])

    def test_duda_que_cambia_el_tier_se_descarta_como_antes(self):
        t = _con_duda([K])
        self.fijar_score(4, t)  # justo en el umbral de REVIEW: el «no» (-5) lo baja
        fila = self.correr(3, t)
        self.assertEqual(fila["motivo"], "jev_incierto")
        self.assertNotIn("dudas_irrelevantes", fila)

    def test_mas_dudas_que_la_tolerancia_se_descarta(self):
        t = _con_duda([K, "hug_the_query"])
        self.fijar_score(30, t)
        self.assertEqual(self.correr(1, t)["motivo"], "jev_incierto")
        self.assertIn("dudas_irrelevantes", self.correr(2, t))

    def test_confianza_baja_tolerada_conserva_el_veredicto(self):
        t = _con_duda([K], incierto=False)
        self.fijar_score(30, t)
        self.assertEqual(j.comparar(self.p, self.cfg, ACTIVO, t)["resultados"][0]["motivo"],
                         "confianza_baja")
        fila = self.correr(1, t)
        self.assertEqual(fila["dudas_irrelevantes"]["criterios"], [K])
        self.assertIn(K, fila["criterios_confianza_baja"])

    def test_tolerada_entra_en_la_comparacion(self):
        t = _con_duda([K])
        self.fijar_score(30, t)
        r = j.comparar(self.p, self.cfg, self.capa(1), t)
        self.assertEqual(r["comparacion"]["total"], 1)
        self.assertEqual(r["sin_propuesta"], 0)


    def test_incierto_core_prueba_tambien_la_exclusion(self):
        # La propuesta se puntúa sin el incierto: esa combinación debe estar.
        _, core = j._opciones(self.cfg)[K]
        self.assertTrue(core)
        t = _con_duda([K])
        self.fijar_score(30, t)
        fila = self.correr(1, t)
        n = len(j._opciones(self.cfg)[K][0])
        self.assertEqual(fila["dudas_irrelevantes"]["combinaciones"], n + 1)
        prop = fila["propuesta"]["score"]
        di = fila["dudas_irrelevantes"]
        self.assertTrue(di["score_min"] <= prop <= di["score_max"])


class TestHibrido(_Base):
    modo = "hibrido"

    def test_incierto_tolerado_obliga_a_reevaluar(self):
        # Falta su veredicto: el principal lo evalúa; nunca se rellena.
        t = _con_duda([K])
        self.fijar_score(30, t)
        fila = self.correr(1, t)
        self.assertIn("dudas_irrelevantes", fila)
        self.assertTrue(fila["usar_principal"])
        self.assertEqual(fila["motivo"], "reevaluar_tier_umbral_o_confianza")
        self.assertNotIn(K, fila["payload_scoring"]["verdicts"])

    def test_confianza_baja_tolerada_tambien_obliga_a_reevaluar(self):
        # En un triaje real no entra un veredicto dudoso (decisión del
        # mantenedor, PR #141): solo queda la anotación.
        t = _con_duda([K], incierto=False)
        self.fijar_score(30, t)
        fila = self.correr(1, t)
        self.assertIn("dudas_irrelevantes", fila)
        self.assertTrue(fila["usar_principal"])
        self.assertEqual(fila["motivo"], "reevaluar_tier_umbral_o_confianza")

    def test_sin_dudas_la_propuesta_sigue_validandose(self):
        self.fijar_score(30, respuesta)
        fila = self.correr(1, respuesta)
        self.assertNotIn("dudas_irrelevantes", fila)
        self.assertEqual(fila["motivo"], "propuesta_validada")

    def test_cambio_de_tier_descarta_en_hibrido(self):
        t = _con_duda([K], incierto=False)
        self.fijar_score(4, t)
        self.assertEqual(self.correr(3, t)["motivo"], "confianza_baja")


class TestConfig(unittest.TestCase):
    def test_valores_admitidos(self):
        for adaptador in (j, d):
            with self.subTest(adaptador=adaptador.__name__):
                self.assertEqual(adaptador.DEFAULT["tolerancia_dudas"], 0)
                for bueno in (0, 1, 3):
                    capa = dict(ACTIVO, tolerancia_dudas=bueno)
                    self.assertEqual(adaptador._config(capa)["tolerancia_dudas"], bueno)
                for malo in (4, -1, True, "1", 1.0, None):
                    with self.assertRaises(nc.ErrorClasificador) as cm:
                        adaptador._config(dict(ACTIVO, tolerancia_dudas=malo))
                    self.assertEqual(str(cm.exception), "tolerancia_dudas_invalida")

    def test_limite_de_combinaciones(self):
        _, cfg = lote()
        activos = j._opciones(cfg)
        e = {"id": "1", "control": {"hard_rules": [], "extra_points": 0,
             "forzar_reply_needed": False, "tier_maximo": None, "remitente_en_historial": False}}
        v = {"verdicts": {k: sorted(o)[0] for k, (o, _) in activos.items()}, "inciertos": []}
        dudosos = sorted(activos)[:3]
        with patch.object(nc, "MAX_COMBINACIONES_DUDAS", 1):
            self.assertIsNone(nc._dudas_irrelevantes(e, v, dudosos, activos, cfg, 3))


if __name__ == "__main__":
    unittest.main()
