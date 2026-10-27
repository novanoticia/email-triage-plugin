"""Huellas de plantilla con retoques (v3.22.11), solo informativas.

Prueba real 2026-10-26: el principal escribió los veredictos de 47 correos
con un diccionario por defecto y 1-3 retoques por correo
(`u('M59', OPI, dict(...))`). Un retoque basta para que no sean idénticos
y `alerta_plantilla` no salta. Dos huellas nuevas lo señalan sin frenar:
criterios inmóviles en un lote variado y vecinos cercanos en tiers
distintos. Un lote homogéneo de promociones honradas no debe saltar.
Sin red; tempfiles.
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

from tests import DIR_SCRIPTS
import triage_helpers as th

CRITERIOS = ["c%02d" % i for i in range(30)]
SID = "20261026-164000"
CFG = {
    "criterios_epistemicos": {
        c: {"activo": True, "core": True, "eje": "valor_decisional",
            "si": 1, "no": -1} for c in CRITERIOS},
    "scoring": {"ejes": {"valor_decisional": [-30, 30]}},
    "tiers": {"reply_needed": 10, "review": 4, "reading_later": 0,
              "archive": -1},
}
# Base de la plantilla: 15 «si» y 15 «no» -> score 0 (READING_LATER).
BASE = {c: ("si" if i < 15 else "no") for i, c in enumerate(CRITERIOS)}


def plantilla_con_retoques():
    """El patrón del log: base común + 1-2 retoques en pocos criterios,
    que reparten los correos entre tres tiers."""
    lote = []
    for k in range(4):   # no->si en uno: +2 -> READING_LATER
        lote.append(dict(BASE, **{CRITERIOS[15 + k % 3]: "si"}))
    for k in range(4):   # no->si en dos: +4 -> REVIEW
        lote.append(dict(BASE, **{CRITERIOS[15 + k % 3]: "si",
                                  CRITERIOS[18 + k % 2]: "si"}))
    for k in range(4):   # si->no en uno: -2 -> ARCHIVE
        lote.append(dict(BASE, **{CRITERIOS[k % 3]: "no"}))
    return lote


def evaluacion_honesta(n=14, semilla=7):
    """Veredictos que varían de verdad, criterio a criterio."""
    azar = random.Random(semilla)
    return [{c: azar.choice(["si", "no", "si", "no", "parcial"])
             for c in CRITERIOS} for _ in range(n)]


def promociones_honestas(n=10):
    """Diez promociones casi iguales que acaban todas en ARCHIVE."""
    todo_no = {c: "no" for c in CRITERIOS}
    return [dict(todo_no, **({CRITERIOS[k % 5]: "si"} if k % 2 else {}))
            for k in range(n)]


def puntuar(veredictos):
    return th.cmd_scoring_dispatch(
        {"emails": [{"id": i, "verdicts": v} for i, v in enumerate(veredictos, 1)]},
        CFG)


class TestHuellas(unittest.TestCase):
    def test_el_patron_del_log_salta_por_las_dos_huellas(self):
        out = puntuar(plantilla_con_retoques())
        self.assertNotIn("alerta_plantilla", out)   # el freno viejo no lo ve
        self.assertEqual({r["tier"] for r in out["resultados"]},
                         {"READING_LATER", "REVIEW", "ARCHIVE"})
        h = out["huellas_plantilla"]
        self.assertGreaterEqual(h["criterios_inmoviles"]["n"], th.UMBRAL_INMOVILES)
        self.assertEqual(h["criterios_inmoviles"]["tiers"], 3)
        self.assertGreaterEqual(h["plantilla_cercana"]["correos"], 5)
        marcados = [r["id"] for r in out["resultados"] if r.get("plantilla_cercana")]
        self.assertEqual(marcados, h["plantilla_cercana"]["ids"])
        self.assertIn("informativo", h["aviso"])

    def test_evaluacion_honesta_no_salta(self):
        out = puntuar(evaluacion_honesta())
        self.assertGreaterEqual(len({r["tier"] for r in out["resultados"]}), 2)
        self.assertNotIn("huellas_plantilla", out)
        self.assertFalse(any(r.get("plantilla_cercana") for r in out["resultados"]))

    def test_promociones_homogeneas_no_saltan(self):
        out = puntuar(promociones_honestas())
        self.assertEqual({r["tier"] for r in out["resultados"]}, {"ARCHIVE"})
        self.assertNotIn("huellas_plantilla", out)

    def test_lote_pequeno_no_mide_inmoviles(self):
        out = puntuar(plantilla_con_retoques()[:9])
        self.assertNotIn("criterios_inmoviles", out.get("huellas_plantilla", {}))

    def test_items_raros_no_revientan(self):
        lote = {"emails": [{"id": i, "verdicts": v}
                           for i, v in enumerate(plantilla_con_retoques())]}
        lote["emails"] += [None, 3, {"id": "x", "verdicts": "texto"},
                           {"id": "y", "verdicts": {"c00": object(), "c01": [1]}}]
        out = th.cmd_scoring_dispatch(lote, CFG)
        self.assertIn("huellas_plantilla", out)
        json.dumps(out, default=str)
        self.assertEqual(th._huellas_plantilla([("a", None, None), (1, {"x": {1}}, 3)]),
                         (None, []))

    def test_no_frena_registrar(self):
        with tempfile.TemporaryDirectory() as d:
            r = th.cmd_registrar(os.path.join(d, "s.jsonl"), {
                "event": "move", "message_id": "<a@b>", "to_folder": "X",
                "score": -2, "plantilla_cercana": True,
                "modo_scoring": "determinista"})
            self.assertTrue(r["ok"], r)


class TestRevisionUltra(unittest.TestCase):
    """/code-review ultra sobre el PR #128 (hallazgos 1-8)."""

    def test_1_resultados_sin_id_no_se_cuentan_como_vecinos(self):
        # Cinco pasadas del mismo correo sin id, con un criterio que va y
        # viene y cambia el tier: no son cinco correos casi iguales.
        pasadas = []
        for k in range(5):
            out = th.cmd_scoring(dict(verdicts=dict(BASE, c15="si" if k % 2 else "no",
                                                   c16="si" if k % 2 else "no")), CFG)
            pasadas.append(out)
        self.assertGreater(len({p["tier"] for p in pasadas}), 1)
        self.assertEqual(th._filas_desglose(pasadas), [])
        self.assertEqual(th._huellas_plantilla(th._filas_desglose(pasadas)), (None, []))

    def test_2_desglose_roto_no_lanza(self):
        raros = [{"id": 1, "tier": "REVIEW", "criterios": 5, "no_evaluados": 3},
                 {"id": 2, "tier": "REVIEW", "criterios": [{"criterio": [1]}]},
                 {"id": 3, "criterios": [None, "x", {"veredicto": "si"}],
                  "no_evaluados": [{"criterio": {"a": 1}}]},
                 "texto", 7]
        filas = th._filas_desglose(raros)
        self.assertEqual([f[0] for f in filas], [1, 2, 3])
        self.assertEqual(th._huellas_plantilla(filas), (None, []))
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "s.jsonl")
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": "x", "desglose": {"resultados": raros}}) + "\n")
            self.assertIsNone(th._huellas_desglose(ruta))

    def test_3_vecinos_iguales_que_la_version_cuadratica(self):
        # La búsqueda optimizada (cada par una vez, salida anticipada) marca
        # lo mismo que la comparación directa par a par.
        azar = random.Random(3)
        lote = [dict(v, **{CRITERIOS[azar.randrange(30)]: "parcial"})
                for v in plantilla_con_retoques() * 3]
        filas = [(i, v, ["REVIEW", "ARCHIVE", "READING_LATER"][i % 3])
                 for i, v in enumerate(lote)]
        esperado = []
        for i, (_, va, ta) in enumerate(filas):
            vec = [tb for j, (_, vb, tb) in enumerate(filas) if j != i and
                   sum(1 for c in set(va) | set(vb) if va.get(c) != vb.get(c))
                   <= th.DIST_CERCANA]
            if len(vec) >= th.MIN_VECINOS_CERCANA and len(set(vec) | {ta}) >= 2:
                esperado.append(i)
        self.assertEqual(th._metricas_plantilla(filas)["cercanos"], esperado)

    def test_4_y_6_lote_grande_no_publica_huella(self):
        n = th.MAX_FILAS_HUELLAS + 1
        lote = (plantilla_con_retoques() * (n // 12 + 1))[:n]
        out = puntuar(lote)
        self.assertNotIn("huellas_plantilla", out)
        self.assertEqual(out["huellas_plantilla_omitidas"]["motivo"], "lote_grande")
        self.assertFalse(any(r.get("plantilla_cercana") for r in out["resultados"]))
        diag = th.cmd_diagnostico_plantillas([("grande", {"resultados": out["resultados"]})])
        self.assertEqual(diag["sesiones"][0]["omitidas"]["motivo"], "lote_grande")
        self.assertEqual(diag["resumen"]["sesiones"], 0)
        self.assertEqual(diag["resumen"]["con_omitidas"], 1)

    def test_5_scoring_y_calibracion_miden_los_mismos_veredictos(self):
        # Criterios desconocidos y valores inválidos: el scoring los ignora y
        # las huellas no deben contarlos ni en scoring ni en la calibración.
        # Dos inválidos que se compensan (un «si» y un «no» fuera): el score
        # no cambia y el lote sigue en tres tiers.
        lote = [dict(v, **{"desconocido_%d" % k: "no" for k in range(12)},
                     c03="valor_raro", c29="valor_raro")
                for v in plantilla_con_retoques()]
        out = puntuar(lote)
        diag = th.cmd_diagnostico_plantillas([("s", {"resultados": out["resultados"]})])
        sesion = diag["sesiones"][0]
        self.assertEqual(len({r["tier"] for r in out["resultados"]}), 3)
        self.assertEqual(sesion["criterios"], 28)  # 2 inválidos y 12 desconocidos fuera
        self.assertEqual(sesion["saltaria"],
                         sorted(k for k in out["huellas_plantilla"] if k != "aviso"))
        self.assertEqual(out["huellas_plantilla"]["criterios_inmoviles"]["de"], 28)

    def test_7_modo_veloz_avisa_de_que_no_puede_saltar(self):
        core = CRITERIOS[:13]
        cfg = json.loads(json.dumps(CFG))
        cfg["criterios_epistemicos"] = {c: cfg["criterios_epistemicos"][c] for c in core}
        cfg["tiers"] = {"reply_needed": 100, "review": 8, "reading_later": 6,
                        "archive": 5}
        base = {c: ("si" if i < 9 else "no") for i, c in enumerate(core)}  # 5
        lote = ([dict(base, c09="si")] * 4            # 7 -> READING_LATER
                + [dict(base, c09="si", c10="si")] * 4  # 9 -> REVIEW
                + [dict(base, c00="no")] * 4)           # 3 -> ARCHIVE
        out = th.cmd_scoring_dispatch(
            {"emails": [{"id": i, "verdicts": v} for i, v in enumerate(lote, 1)]}, cfg)
        self.assertEqual(len({r["tier"] for r in out["resultados"]}), 3)
        self.assertNotIn("huellas_plantilla", out)
        om = out["huellas_plantilla_omitidas"]
        self.assertEqual(om["motivo"], "pocos_criterios")
        self.assertEqual(om["huellas"], ["criterios_inmoviles", "plantilla_cercana"])
        self.assertIn("no prueba que no haya", om["aviso"])
        # Con los 30 criterios no hay aviso de omisión.
        self.assertNotIn("huellas_plantilla_omitidas", puntuar(plantilla_con_retoques()))

    def test_8_criterios_raros_honestos_falso_positivo_conocido(self):
        """Hallazgo 8 (plausible, sin confirmar con datos reales): en un
        triaje honesto muchos criterios son «no» casi siempre. Con 16 así y
        14 que varían, en tres tiers, `criterios_inmoviles` salta HOY. El
        test fija ese comportamiento para que el cambio de umbral, cuando
        se calibre con `diagnostico-plantillas`, sea visible y deliberado."""
        azar = random.Random(11)
        raros, vivos = CRITERIOS[:16], CRITERIOS[16:]
        cfg = json.loads(json.dumps(CFG))
        for c in raros:                 # un «no» raro no resta: es lo normal
            cfg["criterios_epistemicos"][c]["no"] = 0
        lote = []
        for k in range(12):
            v = {c: "no" for c in raros}
            if k == 0:
                v[raros[0]] = "si"      # un criterio raro que salta una vez
            v.update({c: azar.choice(["si", "no"]) for c in vivos})
            lote.append(v)
        out = th.cmd_scoring_dispatch(
            {"emails": [{"id": i, "verdicts": v} for i, v in enumerate(lote, 1)]}, cfg)
        self.assertEqual(len({r["tier"] for r in out["resultados"]}), 3)
        h = out.get("huellas_plantilla", {})
        self.assertNotIn("plantilla_cercana", h)   # los vecinos no lo confunden
        self.assertIn("criterios_inmoviles", h)    # falso positivo conocido
        self.assertEqual(h["criterios_inmoviles"]["n"], 16)


class TestInformeYCalibracion(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.d.name
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))
        self.desgloses = os.path.join(self.d.name, "desgloses")

    def registrar(self, sid, *salidas):
        for salida in salidas:
            r = th.cmd_registrar(os.path.join(self.desgloses, sid + ".jsonl"),
                                 {"ts": "2026-10-26T16:40:00+00:00", "desglose": salida})
            self.assertTrue(r.get("ok"), r)

    def informe(self):
        r = th.cmd_informe({"session_id": SID, "modo": "simulacion",
                            "modo_scoring": "determinista",
                            "unidades": [{"n": 1, "tier": "ARCHIVE", "score": -2,
                                          "asunto": "x", "remitente": "p@x.com",
                                          "fecha": "26/10", "mids": ["<m1>"],
                                          "accion": "propuesto"}]})
        self.assertTrue(r["ok"], r)
        with open(r["ruta"], encoding="utf-8") as fh:
            return r, fh.read()

    def test_informe_avisa_sin_frenar(self):
        self.registrar(SID, puntuar(plantilla_con_retoques()))
        r, md = self.informe()
        self.assertIn("criterios_inmoviles", r["huellas_plantilla"])
        self.assertIn("Posible plantilla con retoques", md)
        self.assertIn("informativo", md)

    def test_informe_honesto_o_sin_desglose_no_cambia(self):
        r, md = self.informe()
        self.assertNotIn("huellas_plantilla", r)
        self.registrar(SID, puntuar(evaluacion_honesta()))
        r, md = self.informe()
        self.assertNotIn("huellas_plantilla", r)
        self.assertNotIn("Posible plantilla", md)

    def test_ultima_pasada_manda(self):
        # Si al repuntuar se evaluó de verdad, la huella se apaga.
        self.registrar(SID, puntuar(plantilla_con_retoques()),
                       puntuar(evaluacion_honesta(n=12)))
        r, _ = self.informe()
        self.assertNotIn("huellas_plantilla", r)

    def test_diagnostico_por_sesion(self):
        self.registrar("s-plantilla", puntuar(plantilla_con_retoques()))
        self.registrar("s-honesta", puntuar(evaluacion_honesta()))
        self.registrar("s-promos", puntuar(promociones_honestas()))
        rutas = sorted(os.path.join(self.desgloses, f) for f in os.listdir(self.desgloses))
        docs = []
        for ruta in rutas:
            with open(ruta, encoding="utf-8") as fh:
                docs.append((ruta, th._parsear_desglose(fh.read())))
        out = th.cmd_diagnostico_plantillas(docs)
        por = {os.path.basename(x["ruta"]): x for x in out["sesiones"]}
        self.assertEqual(por["s-plantilla.jsonl"]["saltaria"],
                         ["criterios_inmoviles", "plantilla_cercana"])
        self.assertEqual(por["s-honesta.jsonl"]["saltaria"], [])
        self.assertEqual(por["s-promos.jsonl"]["saltaria"], [])
        self.assertGreater(por["s-promos.jsonl"]["inmoviles"], 0)  # métrica en bruto
        self.assertEqual(out["resumen"], {"sesiones": 3, "con_inmoviles": 1,
                                          "con_cercanos": 1, "con_omitidas": 0})

    def diagnosticar(self, ruta):
        with open(ruta, encoding="utf-8") as fh:
            doc = th._parsear_desglose(fh.read())
        return th.cmd_diagnostico_plantillas([(ruta, doc)])

    def test_snapshot_sin_append_tambien_se_mide(self):
        # Revisión Codex P2 (PR #128): `scoring --desglose RUTA` sin
        # `--desglose-append` escribe un JSON sin `pasadas` (KeyError).
        os.makedirs(self.desgloses, exist_ok=True)
        ruta = os.path.join(self.desgloses, "snapshot.json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(puntuar(plantilla_con_retoques()), fh)
        out = self.diagnosticar(ruta)
        self.assertEqual(out["resumen"]["sesiones"], 1, out)
        self.assertIn("criterios_inmoviles", out["sesiones"][0]["saltaria"])

    def test_estados_p2_cuentan_como_en_el_scoring(self):
        # Revisión Codex P2 (PR #128): con contrato_p2, `no_aplica` va a
        # `no_evaluados` y no a `criterios`; la calibración no lo veía.
        cfg = json.loads(json.dumps(CFG))
        cfg["scoring"]["contrato_p2"] = True
        # 11 criterios que nunca se retocan, declarados `no_aplica`; los
        # umbrales se mueven para que el lote siga en tres tiers.
        cfg["tiers"] = {"reply_needed": 100, "review": 12, "reading_later": 10,
                        "archive": 9}
        constantes = [CRITERIOS[14]] + CRITERIOS[20:]
        lote = [dict(v, **{c: "no_aplica" for c in constantes})
                for v in plantilla_con_retoques()]
        salida = th.cmd_scoring_dispatch(
            {"emails": [{"id": i, "verdicts": v} for i, v in enumerate(lote, 1)]}, cfg)
        self.assertEqual({r["tier"] for r in salida["resultados"]},
                         {"READING_LATER", "REVIEW", "ARCHIVE"})
        self.assertIn("huellas_plantilla", salida)
        self.assertTrue(all(len(r.get("no_evaluados", [])) == 11
                            for r in salida["resultados"]))
        self.registrar(SID, salida)
        out = self.diagnosticar(os.path.join(self.desgloses, SID + ".jsonl"))
        self.assertEqual(out["sesiones"][0]["criterios"], 30, out)
        self.assertEqual(out["sesiones"][0]["saltaria"],
                         sorted(k for k in salida["huellas_plantilla"] if k != "aviso"))
        r, _ = self.informe()
        self.assertIn("huellas_plantilla", r)

    def test_cli_lee_la_base_por_defecto_y_no_escribe(self):
        self.registrar("s-plantilla", puntuar(plantilla_con_retoques()))
        with open(os.path.join(self.desgloses, "roto.jsonl"), "w") as fh:
            fh.write("no es json\n")
        antes = sorted(os.listdir(self.d.name))
        r = subprocess.run([sys.executable, os.path.join(DIR_SCRIPTS, "triage_helpers.py"),
                            "diagnostico-plantillas"], capture_output=True, text=True,
                           env=dict(os.environ))
        out = json.loads(r.stdout)
        self.assertTrue(out["ok"], r.stderr)
        self.assertEqual(out["resumen"]["con_inmoviles"], 1)
        self.assertEqual([os.path.basename(x["ruta"]) for x in out["ignorados"]],
                         ["roto.jsonl"])
        self.assertEqual(sorted(os.listdir(self.d.name)), antes)


if __name__ == "__main__":
    unittest.main()
