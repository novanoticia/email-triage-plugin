"""Diagnóstico por criterio y `motivo_detalle` (v3.22.5), Jev y Decisions.

Prueba real: 0 de 48 correos útiles con cada proveedor; el filtro de todo o
nada (un criterio incierto descarta el correo) dejaba la comparación sin datos.
Correos ficticios y transporte simulado: sin red.
"""
import copy
import json
import os
import unittest
from unittest.mock import patch, Mock
from tests.test_jev import lote, respuesta as respuesta_jev
from tests.test_decisions import respuesta as respuesta_decisions, ACTIVO
import clasificadores as nc
import decisions as d
import jev as j

PROVEEDORES = (("jev", j, respuesta_jev, "TYPESAFE_API_KEY"),
               ("decisions", d, respuesta_decisions, "OPENAI_API_KEY"))


def mutar_jev(resp, mutar):
    def t(body, *_):
        r = resp(body)
        mutar(r["answers"])
        return r
    return t


def mutar_decisions(resp, mutar):
    """Aplica la misma mutación sobre la forma dict y la devuelve en listas."""
    def t(body, *_):
        r = resp(body)
        answers = {a["name"]: dict(a, probabilities={x["value"]: x["probability"]
                                                     for x in a["probabilities"]})
                   for a in r["answers"]}
        mutar(answers)
        r["answers"] = [dict(a, probabilities=[{"value": v, "probability": p}
                                               for v, p in a["probabilities"].items()])
                        for a in answers.values()]
        return r
    return t


def poner_incierto(answers):
    k = sorted(answers)[0]
    ops = list(answers[k]["probabilities"])
    answers[k].update(choice=nc.INCIERTO, confidence=1.0,
                      probabilities={o: float(o == nc.INCIERTO) for o in ops})


class TestPorCriterio(unittest.TestCase):
    def comparar(self, nombre, modulo, transporte, clave, n=1):
        p, cfg = lote(n)
        with patch.dict(os.environ, {clave: "ficticia"}):
            return modulo.comparar(p, cfg, ACTIVO, transporte), p, cfg

    def test_incierto_descarta_pero_deja_diagnostico(self):
        for nombre, modulo, resp, clave in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                envolver = mutar_jev if nombre == "jev" else mutar_decisions
                r, p, cfg = self.comparar(nombre, modulo, envolver(resp, poner_incierto), clave)
                self.assertTrue(r["ok"], r)
                fila = r["resultados"][0]
                self.assertEqual(fila["motivo"], nombre + "_incierto")
                self.assertNotIn("propuesta", fila)
                self.assertTrue(fila["usar_principal"]); self.assertFalse(r["permitir_movimientos"])
                pc = fila["por_criterio"]
                activos = nc._opciones(cfg)
                incierto = sorted(activos)[0]
                self.assertEqual(pc["inciertos"], [incierto])
                self.assertEqual(pc["criterios"], len(activos))
                self.assertNotIn(incierto, pc["difieren"])
                # El principal elige la primera opción y el simulado la última:
                # coinciden solo los criterios de una sola opción.
                principal = p["emails"][0]["principal"]["verdicts"]
                for k, dif in pc["difieren"].items():
                    self.assertEqual(dif["principal"], principal[k])
                    self.assertNotEqual(dif["externo"], principal[k])
                self.assertEqual(pc["coinciden"] + len(pc["difieren"]) + 1, len(activos))
                agg = r["comparacion_por_criterio"]
                self.assertEqual(agg["correos_evaluados"], 1)
                self.assertEqual(agg["inciertos"], 1)
                self.assertEqual(agg["por_criterio"][incierto]["inciertos"], 1)
                self.assertEqual(agg["tasa_coincidencia"],
                                 round(pc["coinciden"] / len(activos), 4))
                # El resumen clásico no cambia: sin propuestas, nada comparado.
                self.assertEqual(r["comparacion"]["total"], 0)

    def test_coincidencia_total_con_principal_igual(self):
        def igual_al_principal(body, *_):
            r = respuesta_jev(body)
            for k, a in r["answers"].items():
                elegida = sorted(o for o in a["probabilities"]
                                 if o not in (nc.INCIERTO, nc.NO_APLICA))[0]
                a.update(choice=elegida,
                         probabilities={o: float(o == elegida) for o in a["probabilities"]})
            return r
        r, _, cfg = self.comparar("jev", j, igual_al_principal, "TYPESAFE_API_KEY", n=2)
        agg = r["comparacion_por_criterio"]
        self.assertEqual(agg["correos_evaluados"], 2)
        self.assertEqual(agg["tasa_coincidencia"], 1.0)
        self.assertTrue(all(c["difieren"] == 0 and c["coinciden"] == 2
                            for c in agg["por_criterio"].values()))
        self.assertEqual(r["resultados"][0]["motivo"], "solo_comparacion")

    def test_sin_respuesta_valida_no_hay_por_criterio(self):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            p, cfg = lote()
            r = j.comparar(p, cfg, ACTIVO, Mock())
        self.assertNotIn("por_criterio", r["resultados"][0])
        self.assertEqual(r["comparacion_por_criterio"]["correos_evaluados"], 0)
        self.assertIsNone(r["comparacion_por_criterio"]["tasa_coincidencia"])

    def test_hibrido_no_lleva_diagnostico(self):
        p, cfg = lote()
        for e in p["emails"]:
            del e["principal"]; e["contexto_suficiente"] = True
        with patch.dict(os.environ, {"OPENAI_API_KEY": "ficticia"}):
            r = d.evaluar(p, cfg, dict(ACTIVO, modo="hibrido"), respuesta_decisions)
        self.assertTrue(r["ok"], r)
        self.assertNotIn("comparacion_por_criterio", r)
        self.assertNotIn("por_criterio", r["resultados"][0])


class TestMotivoDetalle(unittest.TestCase):
    def caso(self, nombre, modulo, resp, clave, mutar):
        envolver = mutar_jev if nombre == "jev" else mutar_decisions
        p, cfg = lote()
        with patch.dict(os.environ, {clave: "ficticia"}):
            r = modulo.comparar(p, cfg, ACTIVO, envolver(resp, mutar))
        self.assertTrue(r["ok"], r)
        return r["resultados"][0], p

    def test_causas_de_probabilidades_invalidas(self):
        def suma(a):
            k = sorted(a)[0]
            a[k]["probabilities"][a[k]["choice"]] = 0.9  # fuera de la tolerancia de redondeo

        def rango(a):
            k = sorted(a)[0]
            otra = next(o for o in a[k]["probabilities"] if o != a[k]["choice"])
            a[k]["probabilities"][otra] = -0.5
            a[k]["probabilities"][a[k]["choice"]] = 1.5

        def opciones(a):
            k = sorted(a)[0]
            otra = next(o for o in a[k]["probabilities"] if o != a[k]["choice"])
            del a[k]["probabilities"][otra]

        for nombre, modulo, resp, clave in PROVEEDORES:
            for mutar, causa in ((suma, "suma"), (rango, "rango"), (opciones, "opciones")):
                with self.subTest(proveedor=nombre, causa=causa):
                    fila, p = self.caso(nombre, modulo, resp, clave, mutar)
                    self.assertEqual(fila["motivo"], "probabilidades_invalidas")
                    det = fila["motivo_detalle"]
                    self.assertEqual(det["causa"], causa)
                    self.assertEqual(det["criterio"], sorted(nc._opciones(lote()[1]))[0])
                    if causa == "suma":
                        self.assertAlmostEqual(det["desviacion"], 0.1, places=6)
                    self.assertNotIn("por_criterio", fila)
                    # Solo criterio, causa y números: nada del correo.
                    texto = json.dumps(det)
                    self.assertNotIn(p["emails"][0]["estado"]["texto"][:20], texto)
                    self.assertEqual(set(det) - {"criterio", "causa", "desviacion"}, set())

    def test_opcion_no_maxima(self):
        def no_maxima(a):
            k = sorted(a)[0]
            otra = next(o for o in a[k]["probabilities"] if o != a[k]["choice"])
            a[k]["probabilities"][a[k]["choice"]] = 0.4
            a[k]["probabilities"][otra] = 0.6
        fila, _ = self.caso("jev", j, respuesta_jev, "TYPESAFE_API_KEY", no_maxima)
        self.assertEqual(fila["motivo"], "opcion_no_maxima")
        self.assertAlmostEqual(fila["motivo_detalle"]["diferencia"], 0.2, places=6)

    def test_forma_decisions(self):
        def t(body, *_):
            r = respuesta_decisions(body)
            r["answers"][0]["probabilities"] = {"x": 1.0}
            return r
        p, cfg = lote()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "ficticia"}):
            r = d.comparar(p, cfg, ACTIVO, t)
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "probabilidades_invalidas")
        self.assertEqual(fila["motivo_detalle"]["causa"], "forma")

    def test_error_sigue_siendo_solo_el_codigo(self):
        exc = nc.ErrorClasificador("probabilidades_invalidas", {"criterio": "x", "causa": "suma"})
        self.assertEqual(str(exc), "probabilidades_invalidas")
        self.assertIsNone(nc.ErrorClasificador("http_500").detalle)
        self.assertIs(j.ErrorJev, nc.ErrorClasificador)


def redondear(answers, elegida_p=0.99, otra_p=0.0):
    """Probabilidades a dos decimales: la elegida `elegida_p` y una segunda `otra_p`."""
    for a in answers.values():
        ops = list(a["probabilities"])
        otra = next(o for o in ops if o != a["choice"])
        a["probabilities"] = {o: 0.0 for o in ops}
        a["probabilities"][a["choice"]] = elegida_p
        a["probabilities"][otra] = otra_p


class TestRedondeo(unittest.TestCase):
    """v3.22.6: Jev redondea a dos decimales (prueba real: 20 de 48 con suma 0,99)."""

    def comparar(self, nombre, modulo, resp, clave, mutar):
        envolver = mutar_jev if nombre == "jev" else mutar_decisions
        p, cfg = lote()
        with patch.dict(os.environ, {clave: "ficticia"}):
            return modulo.comparar(p, cfg, ACTIVO, envolver(resp, mutar))

    def test_suma_099_se_acepta_y_se_marca(self):
        for nombre, modulo, resp, clave in PROVEEDORES:
            with self.subTest(proveedor=nombre):
                r = self.comparar(nombre, modulo, resp, clave, redondear)
                fila = r["resultados"][0]
                self.assertEqual(fila["motivo"], "solo_comparacion", fila.get("motivo_detalle"))
                ev = fila["evaluacion_" + ("jev" if nombre == "jev" else "decisions")]
                self.assertEqual(sorted(ev["probabilidades_redondeadas"]), sorted(ev["confianzas"]))
                self.assertTrue(fila["usar_principal"]); self.assertFalse(r["permitir_movimientos"])

    def test_suma_mayor_que_1_no_infla_confianza(self):
        r = self.comparar("jev", j, respuesta_jev, "TYPESAFE_API_KEY",
                          lambda a: redondear(a, 0.99, 0.02))
        ev = r["resultados"][0]["evaluacion_jev"]
        for k, ps in ev["probabilidades"].items():
            n = len(ps)
            sin_normalizar = (0.99 - 1 / n) / (1 - 1 / n)
            self.assertLess(ev["confianzas"][k], sin_normalizar)

    def test_desviacion_grande_sigue_rechazada(self):
        r = self.comparar("jev", j, respuesta_jev, "TYPESAFE_API_KEY",
                          lambda a: redondear(a, 0.90, 0.0))
        fila = r["resultados"][0]
        self.assertEqual(fila["motivo"], "probabilidades_invalidas")
        self.assertEqual(fila["motivo_detalle"]["causa"], "suma")

    def test_limite_exacto_de_redondeo_se_acepta(self):
        # Revisión Codex (PR #123): con 4 opciones el límite es 0,02 y la coma
        # flotante calcula 0.020000000000000018 para [0.93, 0.03, 0.03, 0.03].
        ps = {"a": 0.93, "b": 0.03, "c": 0.03, "d": 0.03}
        v = nc.validar_forma({"k": {"type": "choice", "choice": "a", "probabilities": ps,
                                    "confidence": 0.9}}, {"k": set(ps)}, "jev")
        self.assertEqual(v["verdicts"], {"k": "a"})
        self.assertEqual(v["probabilidades_redondeadas"], ["k"])
        fuera = dict(ps, a=0.88)  # suma 0,97: desviación 0,03 > 0,02
        with self.assertRaises(nc.ErrorClasificador):
            nc.validar_forma({"k": {"type": "choice", "choice": "a", "probabilities": fuera,
                                    "confidence": 0.9}}, {"k": set(ps)}, "jev")

    def test_sin_redondeo_lista_vacia(self):
        p, cfg = lote()
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ficticia"}):
            r = j.comparar(p, cfg, ACTIVO, respuesta_jev)
        self.assertEqual(r["resultados"][0]["evaluacion_jev"]["probabilidades_redondeadas"], [])

    def test_hibrido_con_redondeo_vuelve_al_principal(self):
        def redondear_coherente(answers):
            # Confianza declarada = calculada: solo el redondeo puede forzar la revisión.
            redondear(answers)
            for a in answers.values():
                n = len(a["probabilities"])
                a["confidence"] = (0.99 - 1 / n) / (1 - 1 / n)

        def evaluar(transporte):
            p, cfg = lote()
            for e in p["emails"]:
                del e["principal"]; e["contexto_suficiente"] = True
                e["control"]["extra_points"] = 9  # score 6: REVIEW, lejos de los umbrales
            with patch.dict(os.environ, {"OPENAI_API_KEY": "ficticia"}):
                return d.evaluar(p, cfg, dict(ACTIVO, modo="hibrido"), transporte)["resultados"][0]

        control = evaluar(respuesta_decisions)
        self.assertEqual(control["motivo"], "propuesta_validada", control["propuesta"])
        fila = evaluar(mutar_decisions(respuesta_decisions, redondear_coherente))
        self.assertFalse(fila["evaluacion_decisions"]["discrepancias_confianza"])
        self.assertTrue(fila["usar_principal"])
        self.assertEqual(fila["motivo"], "reevaluar_tier_umbral_o_confianza")


if __name__ == "__main__":
    unittest.main()
