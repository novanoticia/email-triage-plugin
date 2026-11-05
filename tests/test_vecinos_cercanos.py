"""Sesiones de hasta 2000 correos (v3.28.3, decisión del mantenedor).

La regla de tandas de v3.28.2 se quedó en 500 correos por sesión porque
`informe` no aceptaba más, y el freno de plantillas dejaba de medir por
encima de 500 (`lote_grande`): la búsqueda de vecinos comparaba todos los
pares y con 2000 filas tardaba 16 s por `scoring`. `_vecinos_cercanos` da el
mismo resultado comparando solo candidatos (palomar por bloques y filas ya
resueltas). Este test lo fija contra la comparación de todos los pares, que
se copia aquí tal como era. Correos ficticios; sin red.
"""
import random
import unittest

from tests import DIR_SCRIPTS  # noqa: F401  (pone scripts en sys.path)
import triage_helpers as th

TIERS = ["ARCHIVE", "REVIEW", "READING_LATER", "REPLY_NEEDED", None]


def todos_los_pares(validas, aptos):
    """La búsqueda anterior a v3.28.3, sin cambios."""
    claves = {k: set(validas[k][1]) for k in aptos}
    vecinos = {k: 0 for k in aptos}
    tiers_vec = {k: {validas[k][2]} for k in aptos}
    for x, a in enumerate(aptos):
        va, ka = validas[a][1], claves[a]
        for b in aptos[x + 1:]:
            vb, kb = validas[b][1], claves[b]
            dist = len(ka ^ kb)
            if dist > th.DIST_CERCANA:
                continue
            for c in ka & kb:
                if va[c] != vb[c]:
                    dist += 1
                    if dist > th.DIST_CERCANA:
                        break
            if dist <= th.DIST_CERCANA:
                vecinos[a] += 1
                vecinos[b] += 1
                tiers_vec[a].add(validas[b][2])
                tiers_vec[b].add(validas[a][2])
    return vecinos, tiers_vec


def cercanos(validas, aptos, buscar):
    vecinos, tiers_vec = buscar(validas, aptos)
    return sorted(k for k in aptos if vecinos[k] >= th.MIN_VECINOS_CERCANA
                  and len(tiers_vec[k] - {None}) >= 2)


def lote(azar, n, modo):
    criterios = ["c%02d" % i for i in range(azar.choice([20, 22, 30, 34]))]
    base = {c: azar.choice("abc") for c in criterios}
    filas = []
    for i in range(n):
        if modo == "azar":
            vs = {c: azar.choice("abcd") for c in criterios}
        else:   # base común con 0-4 retoques: la huella que se busca
            vs = dict(base)
            for _ in range(azar.randint(0, 4 if modo == "plantilla" else 1)):
                vs[azar.choice(criterios)] = azar.choice("abcd")
        for _ in range(azar.randint(0, 3)):   # criterios sin veredicto
            if azar.random() < 0.4:
                vs.pop(azar.choice(criterios), None)
        filas.append((i, vs, azar.choice(TIERS)))
    return filas


def aptos_de(validas):
    return [k for k in range(len(validas))
            if len(validas[k][1]) >= th.MIN_CRITERIOS_CERCANA]


class TestMismoResultado(unittest.TestCase):
    def test_igual_que_comparar_todos_los_pares(self):
        azar = random.Random(11)
        for it in range(300):
            modo = azar.choice(["azar", "plantilla", "casi"])
            validas = lote(azar, azar.randint(0, 60), modo)
            aptos = aptos_de(validas)
            self.assertEqual(cercanos(validas, aptos, todos_los_pares),
                             cercanos(validas, aptos, th._vecinos_cercanos),
                             (it, modo))

    def test_criterio_ausente_cuenta_como_diferencia(self):
        # Como `len(ka ^ kb)`: 3 ausentes en uno = distancia 3, vecinos;
        # 4 = distancia 4, no.
        base = {"c%02d" % i: "a" for i in range(24)}
        tres = {k: v for k, v in base.items() if k not in ("c00", "c01", "c02")}
        cuatro = {k: v for k, v in tres.items() if k != "c03"}
        validas = [(0, base, "A"), (1, tres, "B"), (2, cuatro, "C")]
        vecinos, _ = th._vecinos_cercanos(validas, [0, 1, 2])
        self.assertEqual(vecinos, {0: 1, 1: 2, 2: 1})


    def test_con_menos_criterios_que_bloques_compara_todos(self):
        # Dos criterios, distancia 2: el palomar solo no la vería.
        validas = [(i, {"a": str(i % 2), "b": str(i % 2)}, t)
                   for i, t in enumerate(["A", "B", "A", "B", "A", "B"])]
        aptos = list(range(len(validas)))
        self.assertEqual(cercanos(validas, aptos, th._vecinos_cercanos),
                         cercanos(validas, aptos, todos_los_pares))
        self.assertEqual(len(cercanos(validas, aptos, th._vecinos_cercanos)), 6)


class TestSesionDe2000(unittest.TestCase):
    def test_el_freno_mide_2000_correos(self):
        filas = lote(random.Random(5), 2000, "plantilla")
        filas = [(i, vs, t) for i, vs, t in filas if vs]
        ev = th._evaluar_huellas(filas)
        self.assertIsNone(ev["omitidas"])
        self.assertTrue(ev["cercanos"])

    def test_tope_de_huellas_e_informe(self):
        self.assertEqual(th.MAX_FILAS_HUELLAS, 2000)
        self.assertEqual(th._INFORME_MAX_UNIDADES, 2000)
        filas = [(i, {"c%02d" % j: str(i) for j in range(25)}, "ARCHIVE")
                 for i in range(th.MAX_FILAS_HUELLAS + 1)]
        self.assertEqual(th._evaluar_huellas(filas)["omitidas"]["motivo"],
                         "lote_grande")


if __name__ == "__main__":
    unittest.main()
