"""El plan no puede pasar de la capa en disco (v3.21.35).

Prueba real 2026-10-21: con `max_llamadas: 30` en config-modelos.yaml (fuera
del rango 1-10, capa inválida) el modelo delegó igual, con un tope de 10
elegido por él, y comparó con «un plan en memoria con lote de 50». El plan es
un JSON que el modelo escribe; el fichero no. Sin red: respuestas sintéticas.
"""
import os
import tempfile
import unittest

from tests import DIR_SCRIPTS  # noqa: F401  (pone scripts/ en sys.path)
import modelos as m
import triage_helpers as th

PLAN = {"ok": True, "modo": "comparar", "delegar": True,
        "modelo_solicitado": "economico-prueba", "proveedor": "anthropic",
        "llamadas_restantes": 10, "tamano_lote": 50, "concurrencia": 1}


def _payload(n=3, plan=None):
    filas = [{"id": str(i), "score": 1, "tier": "ARCHIVE"} for i in range(n)]
    return {"plan": dict(plan or PLAN), "base": filas,
            "propuesta": [dict(f) for f in filas]}


class TestPlanContraCapa(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        viejo = os.environ.get(th.ENV_BASE_ESTADO)
        os.environ[th.ENV_BASE_ESTADO] = self.d.name
        self.addCleanup(lambda: os.environ.pop(th.ENV_BASE_ESTADO, None)
                        if viejo is None
                        else os.environ.__setitem__(th.ENV_BASE_ESTADO, viejo))

    def _capa(self, texto):
        with open(os.path.join(self.d.name, th.NOMBRE_CAPA_MODELOS), "w",
                  encoding="utf-8") as fh:
            fh.write(texto)

    def test_el_caso_real_capa_invalida_no_delega(self):
        self._capa('modo: comparar\nmodelo: ""\nmax_llamadas: 30\n'
                   'tamano_lote: 20\n')
        r = m.comparar(_payload())
        self.assertFalse(r["ok"])
        self.assertEqual(r["motivo"], "capa_modelos_invalida")
        self.assertEqual(r["motivo_capa"], "presupuesto_invalido")
        self.assertTrue(r["usar_principal"])

    def test_plan_mayor_que_la_capa_activa(self):
        self._capa("modo: comparar\nmax_llamadas: 10\ntamano_lote: 20\n")
        r = m.comparar(_payload())  # plan con lote 50 > 20
        self.assertEqual(r["motivo"], "plan_no_coincide_con_capa")
        r = m.comparar(_payload(plan=dict(PLAN, tamano_lote=20,
                                          llamadas_restantes=11)))
        self.assertEqual(r["motivo"], "delegacion_no_autorizada")  # >10
        self._capa("modo: comparar\nmax_llamadas: 5\ntamano_lote: 20\n")
        r = m.comparar(_payload(plan=dict(PLAN, tamano_lote=20,
                                          llamadas_restantes=6)))
        self.assertEqual(r["motivo"], "plan_no_coincide_con_capa")

    def test_plan_dentro_de_la_capa_vale(self):
        self._capa("modo: comparar\nmax_llamadas: 10\ntamano_lote: 20\n")
        r = m.comparar(_payload(plan=dict(PLAN, tamano_lote=20)))
        self.assertTrue(r["ok"], r)
        r = m.comparar(_payload(plan=dict(PLAN, tamano_lote=5,
                                          llamadas_restantes=1)))
        self.assertTrue(r["ok"], r)

    def test_validar_tambien_lo_aplica(self):
        self._capa("modo: hibrido\nmax_llamadas: 30\n")
        r = m.validar({"plan": dict(PLAN, modo="hibrido")})
        self.assertEqual(r["motivo"], "capa_modelos_invalida")

    def test_sin_fichero_o_en_actual_vale_la_sesion(self):
        # La activación «solo para esta sesión» no tiene fichero que la acote.
        self.assertTrue(m.comparar(_payload())["ok"])
        self._capa("modo: actual\n")
        self.assertTrue(m.comparar(_payload())["ok"])

    def test_pista_si_comparar_usa_un_plan_tardio(self):
        # El plan de la última llamada (1 restante) no admite la sesión entera.
        r = m.comparar(_payload(n=30, plan=dict(PLAN, tamano_lote=20,
                                                llamadas_restantes=1)))
        self.assertEqual(r["motivo"], "lote_mayor_que_el_autorizado")
        self.assertIn("primera llamada", r["pista"])

    def test_plan_con_otro_modo_o_modelo(self):
        # Revisión Codex (PR #104): mismos topes, pero otro modo o modelo.
        self._capa("modo: comparar\nmax_llamadas: 10\ntamano_lote: 50\n")
        r = m.comparar(_payload(plan=dict(PLAN, modo="hibrido")))
        self.assertEqual(r["motivo"], "plan_no_coincide_con_capa")
        self._capa('modo: comparar\nmodelo: "fijo"\nmax_llamadas: 10\n'
                   'tamano_lote: 50\n')
        r = m.comparar(_payload())  # economico-prueba != fijo
        self.assertEqual(r["motivo"], "plan_no_coincide_con_capa")
        self.assertTrue(m.comparar(_payload(plan=dict(
            PLAN, modelo_solicitado="fijo")))["ok"])

    def test_planificar_lo_aplica_antes_de_delegar(self):
        # Revisión Codex (PR #104): el freno llega antes de gastar llamadas.
        host = {"proveedor": "anthropic", "modelo_principal": "principal",
                "modelo_economico": "economico-prueba",
                "modelos": [{"id": "economico-prueba",
                             "proveedor": "anthropic"}],
                **{k: True for k in ("delegacion", "seleccion_modelo",
                                     "contexto_aislado", "sin_herramientas",
                                     "misma_conexion")}}
        pedido = {"config": {"modo": "comparar", "max_llamadas": 10,
                             "tamano_lote": 20}, "host": host}
        self.assertTrue(m.planificar(pedido)["delegar"])  # sin fichero
        self._capa("modo: comparar\nmax_llamadas: 30\ntamano_lote: 20\n")
        r = m.planificar(pedido)
        self.assertEqual(r["motivo"], "capa_modelos_invalida")
        self.assertTrue(r["siguiente"].startswith("no delegues"))
        self._capa("modo: comparar\nmax_llamadas: 5\ntamano_lote: 20\n")
        self.assertEqual(m.planificar(pedido)["motivo"],
                         "plan_no_coincide_con_capa")
        self._capa("modo: comparar\nmax_llamadas: 10\ntamano_lote: 20\n")
        self.assertTrue(m.planificar(pedido)["delegar"])


if __name__ == "__main__":
    unittest.main()
