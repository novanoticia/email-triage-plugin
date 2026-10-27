"""Huellas de plantilla acumuladas en la sesión (v3.22.13).

Primera pieza de la evaluación por bloques: si el principal puntúa en
lotes pequeños, las huellas medidas solo sobre cada lote se diluyen (con 4
correos o menos ningún correo puede tener 4 vecinos) y `plantilla_cercana`
no frena nunca. Con `scoring --desglose RUTA --desglose-append` se miden
sobre lo ya puntuado en la sesión más el lote nuevo. Sin red; tempfiles.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from tests import DIR_SCRIPTS
from tests.test_huellas_plantilla import (CFG, evaluacion_honesta,
                                          plantilla_con_retoques)
import triage_helpers as th


def bloques(veredictos, n=3):
    lote = [{"id": "m%02d" % i, "verdicts": v}
            for i, v in enumerate(veredictos, 1)]
    return [{"emails": lote[k:k + n]} for k in range(0, len(lote), n)]


def filas_de(out):
    return [(r["id"], th._veredictos_aceptados(r), r["tier"])
            for r in out["resultados"]]


class TestHuellasAcumuladas(unittest.TestCase):
    def test_por_bloques_sin_acumular_no_salta(self):
        # Lo que pasaba antes: cada bloque de 3, medido solo, sale limpio.
        for b in bloques(plantilla_con_retoques()):
            out = th.cmd_scoring_dispatch(b, CFG)
            self.assertNotIn("huellas_plantilla", out)

    def test_por_bloques_acumulando_salta_y_frena(self):
        previas, marcados, previos = [], [], []
        for b in bloques(plantilla_con_retoques()):
            out = th.cmd_scoring_dispatch(b, CFG, previas=previas)
            marcados += [r["id"] for r in out["resultados"]
                         if r.get("plantilla_cercana")]
            cer = out.get("huellas_plantilla", {}).get("plantilla_cercana", {})
            previos += cer.get("ids_previos", [])
            previas += filas_de(out)
        self.assertEqual(out["huellas_acumuladas"],
                         {"correos_previos": 9, "correos_lote": 3})
        self.assertTrue(marcados)
        # Los de bloques anteriores no llevan la marca en su resultado:
        # se nombran para que el principal la copie o los repuntúe.
        self.assertTrue(previos)
        self.assertIn("aviso_previos", cer)
        # Mismo veredicto que medir el lote entero de una vez.
        entero = th.cmd_scoring_dispatch(
            {"emails": [e for b in bloques(plantilla_con_retoques())
                        for e in b["emails"]]}, CFG)
        self.assertEqual(sorted(set(marcados) | set(previos)),
                         sorted(entero["huellas_plantilla"]["plantilla_cercana"]["ids"]))

    def test_evaluacion_honesta_por_bloques_no_salta(self):
        previas = []
        for b in bloques(evaluacion_honesta()):
            out = th.cmd_scoring_dispatch(b, CFG, previas=previas)
            self.assertNotIn("huellas_plantilla", out)
            previas += filas_de(out)

    def test_repuntuar_un_id_manda_sobre_su_pasada_anterior(self):
        lote = bloques(plantilla_con_retoques(), n=12)[0]
        previas = filas_de(th.cmd_scoring_dispatch(lote, CFG))
        # Se reevalúan los mismos 12 de verdad: lo anterior no cuenta.
        honesto = {"emails": [dict(e, verdicts=v) for e, v in
                              zip(lote["emails"], evaluacion_honesta(12))]}
        out = th.cmd_scoring_dispatch(honesto, CFG, previas=previas)
        self.assertNotIn("huellas_plantilla", out)
        self.assertNotIn("huellas_acumuladas", out)

    def test_previas_raras_no_revientan(self):
        b = bloques(plantilla_con_retoques())[0]
        out = th.cmd_scoring_dispatch(
            b, CFG, previas=[None, ("a",), ("x", "texto", 3), (1, {"c": {1}}, None)])
        json.dumps(out, default=str)
        self.assertEqual(len(out["resultados"]), 3)

    def test_filas_previas_de_fichero_raro(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "s.jsonl")
            self.assertEqual(th._filas_previas(ruta), [])
            with open(ruta, "w") as fh:
                fh.write("no es json\n")
            # Existe pero no se lee: se dice, no se acumula en silencio.
            self.assertEqual(th._filas_previas(ruta), "desglose_ilegible")

    def test_cli_acumula_con_desglose_append(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.yaml")
            with open(cfg, "w") as fh:
                json.dump(CFG, fh)   # JSON es YAML válido
            ruta = os.path.join(d, "desgloses", "s.jsonl")
            salidas = []
            for b in bloques(plantilla_con_retoques()):
                r = subprocess.run(
                    [sys.executable, os.path.join(DIR_SCRIPTS, "triage_helpers.py"),
                     "scoring", "--config", cfg, "--brief",
                     "--desglose", ruta, "--desglose-append"],
                    input=json.dumps(b), capture_output=True, text=True)
                salidas.append(json.loads(r.stdout))
            self.assertNotIn("huellas_acumuladas", salidas[0])
            self.assertNotIn("huellas_plantilla", salidas[0])
            ult = salidas[-1]
            self.assertEqual(ult["huellas_acumuladas"]["correos_previos"], 9)
            self.assertIn("plantilla_cercana", ult["huellas_plantilla"])
            # El desglose escrito trae la misma huella: el informe la ve.
            self.assertIsNotNone(th._huellas_desglose(ruta))
            # Sin --desglose-append no se acumula nada (lo de siempre).
            r = subprocess.run(
                [sys.executable, os.path.join(DIR_SCRIPTS, "triage_helpers.py"),
                 "scoring", "--config", cfg, "--desglose",
                 os.path.join(d, "snap.json")],
                input=json.dumps(bloques(plantilla_con_retoques())[-1]),
                capture_output=True, text=True)
            self.assertNotIn("huellas_acumuladas", json.loads(r.stdout))

    # Revisión Codex (PR #130).
    def test_scoring_individual_tambien_acumula(self):
        lote = [e for b in bloques(plantilla_con_retoques()) for e in b["emails"]]
        previas = filas_de(th.cmd_scoring_dispatch({"emails": lote[:-1]}, CFG))
        uno = th.cmd_scoring_dispatch(lote[-1], CFG, previas=previas)
        envuelto = th.cmd_scoring_dispatch({"emails": [lote[-1]]}, CFG,
                                           previas=previas)
        self.assertEqual(uno.get("plantilla_cercana"),
                         envuelto["resultados"][0].get("plantilla_cercana"))
        self.assertIs(uno["plantilla_cercana"], True)
        self.assertEqual(uno["huellas_acumuladas"]["correos_previos"], 11)
        # Sin previas, el resultado individual no cambia.
        self.assertNotIn("huellas_acumuladas",
                         th.cmd_scoring_dispatch(lote[-1], CFG))

    def test_desglose_truncado_no_acumula_y_lo_dice(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "s.jsonl")
            with open(ruta, "w") as fh:
                fh.write("x" * (th.MAX_INGESTA_BYTES + 1))
            self.assertEqual(th._filas_previas(ruta), "desglose_grande")
            self.assertIsNone(th._huellas_desglose(ruta))
        b = bloques(plantilla_con_retoques())[0]
        out = th.cmd_scoring_dispatch(b, CFG, previas="desglose_grande")
        self.assertEqual(out["huellas_acumuladas_omitidas"]["motivo"],
                         "desglose_grande")
        self.assertNotIn("huellas_acumuladas", out)

    def test_vectores_omite_los_ids_previos(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "s.jsonl")
            previos = []
            for b in bloques(plantilla_con_retoques()):
                out = th.cmd_scoring_dispatch(b, CFG,
                                              previas=th._filas_previas(ruta))
                cer = out.get("huellas_plantilla", {}).get("plantilla_cercana", {})
                previos += cer.get("ids_previos", [])
                th.cmd_registrar(ruta, {"ts": "t", "desglose": out})
            self.assertTrue(previos)
            r = th.cmd_vectores(os.path.join(d, "vectors.jsonl"), ruta,
                                {"session_id": "s", "message_ids":
                                 {i: "<%s@x>" % i for i in previos}}, CFG)
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["escritos"], 0, r)
            self.assertEqual({o["motivo"] for o in r["omitidos"]},
                             {"veredictos casi iguales (plantilla_cercana)"})

    def test_vectores_honestos_por_bloques_se_escriben(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "s.jsonl")
            ids = []
            # Solo «si»/«no»: el vector exige todos los core válidos.
            honesta = [{c: ("no" if v == "parcial" else v) for c, v in e.items()}
                       for e in evaluacion_honesta()]
            for b in bloques(honesta):
                out = th.cmd_scoring_dispatch(b, CFG,
                                              previas=th._filas_previas(ruta))
                self.assertNotIn("huellas_plantilla", out)
                ids += [e["id"] for e in b["emails"]]
                th.cmd_registrar(ruta, {"ts": "t", "desglose": out})
            r = th.cmd_vectores(os.path.join(d, "vectors.jsonl"), ruta,
                                {"session_id": "s", "message_ids":
                                 {i: "<%s@x>" % i for i in ids}}, CFG)
            self.assertEqual(r["escritos"], len(ids), r)

    # Revisión Codex (PR #131): veredictos idénticos repartidos en bloques.
    def test_identicos_entre_bloques_frenan(self):
        iguales = [plantilla_con_retoques()[0]] * 6
        b1, b2 = bloques(iguales)
        # Cada bloque de 3, solo, no llega a 5 iguales.
        self.assertNotIn("alerta_plantilla", th.cmd_scoring_dispatch(b2, CFG))
        o1 = th.cmd_scoring_dispatch(b1, CFG, previas=[])
        self.assertNotIn("alerta_plantilla", o1)
        o2 = th.cmd_scoring_dispatch(b2, CFG, previas=filas_de(o1))
        self.assertTrue(all(r.get("plantilla") for r in o2["resultados"]))
        g = o2["alerta_plantilla"]["grupos"][0]
        self.assertTrue(g["acumulado"])
        self.assertEqual(sorted(g["ids_previos"]), ["m01", "m02", "m03"])
        self.assertIn("aviso_previos", o2["alerta_plantilla"])
        # registrar lo frena como siempre.
        with tempfile.TemporaryDirectory() as d:
            r = th.cmd_registrar(os.path.join(d, "s.jsonl"), {
                "event": "move", "message_id": "<a@b>", "to_folder": "X",
                "score": 0, "plantilla": True, "modo_scoring": "determinista"})
            self.assertIs(r["ok"], False)

    def test_vectores_omite_los_identicos_previos(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "s.jsonl")
            for b in bloques([plantilla_con_retoques()[0]] * 6):
                out = th.cmd_scoring_dispatch(b, CFG,
                                              previas=th._filas_previas(ruta))
                th.cmd_registrar(ruta, {"ts": "t", "desglose": out})
            r = th.cmd_vectores(os.path.join(d, "vectors.jsonl"), ruta,
                                {"session_id": "s", "message_ids":
                                 {"m01": "<m01@x>"}}, CFG)
            self.assertEqual(r["escritos"], 0, r)
            self.assertEqual(r["omitidos"][0]["motivo"], "veredictos de plantilla")

    def test_menos_de_cinco_iguales_en_la_sesion_no_frenan(self):
        iguales = [plantilla_con_retoques()[0]] * 4
        b1, b2 = bloques(iguales)
        o1 = th.cmd_scoring_dispatch(b1, CFG, previas=[])
        o2 = th.cmd_scoring_dispatch(b2, CFG, previas=filas_de(o1))
        self.assertNotIn("alerta_plantilla", o2)


if __name__ == "__main__":
    unittest.main()
