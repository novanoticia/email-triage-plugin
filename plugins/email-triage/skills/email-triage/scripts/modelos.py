#!/usr/bin/env python3
"""Contratos locales para la delegación nativa opcional.

No invoca modelos, no accede a red/buzón y no escribe archivos. El host ejecuta
la delegación; este módulo comprueba elegibilidad, respuestas y comparaciones.
Entrada y salida JSON por stdin/stdout, sin contenido de correos en argumentos.
"""
import argparse
import copy
import json
import math
import sys

import triage_helpers as th


PROVEEDORES_NATIVOS = ("anthropic", "openai")


def _error(motivo):
    return {"ok": False, "motivo": motivo, "usar_principal": True}


def _entero(v, minimo, maximo):
    return type(v) is int and minimo <= v <= maximo


def _texto(v):
    return isinstance(v, str) and bool(v.strip())


def planificar(p):
    """Capacidades declaradas por el host, nunca por el correo/especialista.

    La misma marca comercial no basta: se exige la misma conexión y que el
    cliente pueda aislar el contexto y prohibir herramientas al especialista.
    """
    cfg = p.get("config", {})
    # Las reglas del config son las de `validar-config` (capa_modelos).
    motivo = th._motivo_capa_modelos(cfg)
    if motivo:
        return _error(motivo)
    modo = cfg.get("modo", "actual")
    if modo == "actual":
        return {"ok": True, "modo": "actual", "delegar": False}
    limite = cfg.get("max_llamadas", 2)
    lote = cfg.get("tamano_lote", 25)
    usadas = p.get("llamadas_realizadas", 0)
    if not _entero(usadas, 0, 1000):
        return _error("presupuesto_invalido")
    if usadas >= limite:
        return _error("presupuesto_agotado")
    host = p.get("host")
    if not isinstance(host, dict):
        return _error("capacidades_desconocidas")
    necesarias = ("delegacion", "seleccion_modelo", "contexto_aislado",
                  "sin_herramientas", "misma_conexion")
    if any(host.get(k) is not True for k in necesarias):
        return _error("delegacion_nativa_no_verificada")
    proveedor = host.get("proveedor")
    if proveedor not in PROVEEDORES_NATIVOS:
        return _error("proveedor_no_admitido")
    modelo = cfg.get("modelo", "") or host.get("modelo_economico")
    if not _texto(modelo):
        return _error("modelo_no_identificado")
    disponibles = host.get("modelos")
    if not isinstance(disponibles, list) or not any(
        isinstance(m, dict) and m.get("id") == modelo
        and m.get("proveedor") == proveedor for m in disponibles
    ):
        return _error("modelo_no_disponible_en_el_proveedor")
    if not _texto(host.get("modelo_principal")):
        return _error("modelo_principal_desconocido")
    if modelo == host["modelo_principal"]:
        return _error("modelo_ya_es_el_principal")
    contra_capa = _contra_capa(modo, modelo, lote, limite)
    if contra_capa:
        return contra_capa
    return {"ok": True, "modo": modo, "delegar": True,
            "modelo_solicitado": modelo, "proveedor": proveedor,
            "llamadas_restantes": limite - usadas, "tamano_lote": lote,
            "concurrencia": 1}


CLAVES_PLAN = {"ok", "modo", "delegar", "modelo_solicitado", "proveedor",
               "llamadas_restantes", "tamano_lote", "concurrencia"}


def _contra_capa(modo, modelo, lote, llamadas):
    """v3.21.35 (prueba real 2026-10-21: con `max_llamadas: 30` la capa era
    inválida, pero el modelo delegó con un tope de 10 elegido por él y
    comparó con «un plan en memoria con lote de 50»). El config y el plan
    son JSON que el modelo puede escribir a mano; la capa en disco no. Si
    el fichero existe, manda: inválida = no hay delegación; activa = mismo
    modo, mismo modelo si lo fija, y sin pasar de sus límites. Ausente o en
    `actual`, la activación solo para esta sesión sigue valiendo. Lo aplican
    `planificar` (antes de gastar llamadas) y `validar`/`comparar`
    (revisión Codex, PR #104)."""
    capa = th._leer_capa_modelos(th.base_estado())
    if capa.get("estado") == "invalida":
        return dict(_error("capa_modelos_invalida"),
                    motivo_capa=capa.get("motivo"),
                    siguiente=capa.get("siguiente"))
    if capa.get("estado") == "activa":
        c = capa["config"]
        if (modo != c["modo"] or (c["modelo"] and modelo != c["modelo"])
                or lote > c["tamano_lote"] or llamadas > c["max_llamadas"]):
            return _error("plan_no_coincide_con_capa")
    return None


def _plan_autoriza(p):
    """v3.21.17 (prueba real comparar, 2026-10-19): `planificar` devolvió
    delegacion_nativa_no_verificada y el modelo delegó igualmente; validar
    y comparar procesaron la respuesta sin preguntar. Ahora exigen el `plan`
    literal de planificar con delegar: true. No impide llamar al
    especialista (eso no lo controla ningún script), pero su respuesta ya no
    tiene vía oficial para contar si el plan no la autorizó."""
    plan = p.get("plan")
    if (not isinstance(plan, dict) or plan.get("ok") is not True
            or plan.get("delegar") is not True
            or plan.get("modo") not in ("comparar", "hibrido")
            or set(plan) != CLAVES_PLAN
            or not _texto(plan.get("modelo_solicitado"))
            or plan.get("proveedor") not in PROVEEDORES_NATIVOS
            or not _entero(plan.get("concurrencia"), 1, 1)
            or not _entero(plan.get("llamadas_restantes"), 1, 10)
            or not _entero(plan.get("tamano_lote"), 1, 50)):
        return _error("delegacion_no_autorizada")
    # El lote no puede ser mayor que el que autorizó el plan. Reusar un plan
    # viejo tras agotar max_llamadas no se puede impedir sin estado (este
    # módulo no escribe): es una huella, no una prueba, como los otros frenos.
    # `validar` va por lote; `comparar` agrega la sesión entera (varias
    # llamadas), así que su tope es tamano_lote × llamadas_restantes del
    # plan de la primera llamada (revisión Codex P2, PR #86).
    topes = {"esperados": plan["tamano_lote"],
             "base": plan["tamano_lote"] * plan["llamadas_restantes"]}
    for clave, tope in topes.items():
        filas = p.get(clave)
        if isinstance(filas, list) and len(filas) > tope:
            error = _error("lote_mayor_que_el_autorizado")
            if clave == "base":
                error["pista"] = "comparar usa el plan de la primera llamada"
            return error
    return _contra_capa(plan["modo"], plan["modelo_solicitado"],
                        plan["tamano_lote"], plan["llamadas_restantes"])


def _indexar(filas):
    if not isinstance(filas, list) or not filas:
        raise ValueError("lote_vacio_o_invalido")
    indice = {}
    for fila in filas:
        if not isinstance(fila, dict) or not _texto(fila.get("id")):
            raise ValueError("id_invalido")
        if fila["id"] in indice:
            raise ValueError("id_duplicado")
        indice[fila["id"]] = fila
    return indice


def _criterios(cfg):
    criterios = cfg.get("criterios_epistemicos")
    if not isinstance(criterios, dict) or not criterios:
        raise ValueError("criterios_ausentes")
    activos = {}
    comportamiento = cfg.get("comportamiento_veloz", {})
    if not isinstance(comportamiento, dict):
        raise ValueError("comportamiento_invalido")
    solo_core = comportamiento.get("solo_criterios_core", False)
    for k, v in criterios.items():
        if not _texto(k) or not isinstance(v, dict):
            raise ValueError("criterio_invalido")
        if v.get("activo", True) and (not solo_core or v.get("core")):
            opciones = {o for o in v if o not in th._META_CRIT}
            if not opciones or any(not isinstance(o, str) for o in opciones):
                raise ValueError("opciones_invalidas")
            activos[k] = (opciones, bool(v.get("core")))
    if not activos:
        raise ValueError("sin_criterios_activos")
    return activos


def _validar_fila(fila, criterios):
    campos = {"id", "verdicts", "no_aplica", "evidencias", "dudas", "resumen"}
    # v3.21.36: `eco` (lo que el especialista recibió) es opcional aquí; lo
    # exige `validar` si el esperado trae `ancla_extracto`.
    if set(fila) - {"eco"} != campos:
        return "campos_incorrectos"
    vs, na, ev = (fila[k] for k in ("verdicts", "no_aplica", "evidencias"))
    if not all(isinstance(v, dict) for v in (vs, na, ev)):
        return "veredictos_invalidos"
    if set(vs) & set(na) or set(vs) | set(na) != set(criterios):
        return "cobertura_incompleta_o_desconocida"
    if set(ev) != set(vs) or not all(_texto(v) for v in ev.values()):
        return "evidencias_ausentes"
    for k, v in vs.items():
        if not isinstance(v, str) or v not in criterios[k][0]:
            return "opcion_invalida"
    for k, razon in na.items():
        if criterios[k][1] or not _texto(razon):
            return "criterio_core_omitido_o_sin_justificacion"
    if not isinstance(fila["dudas"], list) or not all(
            _texto(v) for v in fila["dudas"]):
        return "dudas_invalidas"
    if not _texto(fila["resumen"]):
        return "resumen_ausente"
    return None


def validar(p):
    """Valida por correo y calcula con scoring existente, sin cambiar sus reglas.

    `esperados[].control` procede del principal ANTES de delegar (4.A/4.C/S0).
    El especialista solo aporta veredictos; nunca caps, boosts ni movimientos.
    La validez de evidencia textual sigue exigiendo revisión del principal.
    """
    no_autorizada = _plan_autoriza(p)
    if no_autorizada:
        return no_autorizada
    # v3.21.25: Claude Code lista el evaluador con `tools: []` como «All
    # tools», pero arranca sin herramientas (sondeo 2026-10-20). El plan se
    # fía del frontmatter; esto lo vigila: `acciones_especialista` es el
    # `tool_uses` que el HOST informa de la llamada. Cualquier acción cuenta
    # como herramienta (revisión Codex P1, PR #94: en Claude Code la entrega
    # no suma; un host que sí la sume queda sin delegación, fail-closed).
    # Opcional.
    acciones = p.get("acciones_especialista")
    if acciones is not None:
        if type(acciones) is not int or acciones < 0:
            return _error("acciones_especialista_invalidas")
        if acciones > 0:
            return _error("especialista_uso_herramientas")
    cfg = p.get("config")
    if not isinstance(cfg, dict):
        return _error("config_invalida")
    criterios = _criterios(cfg)
    esperados = _indexar(p.get("esperados"))
    respuesta = p.get("respuesta")
    if not isinstance(respuesta, dict) or set(respuesta) != {"evaluaciones"}:
        return _error("respuesta_invalida")
    filas = _indexar(respuesta["evaluaciones"])
    if set(filas) - set(esperados):
        return _error("ids_inesperados")
    # v3.21.30 (prueba real 2026-10-21: el principal recortó los extractos
    # de Haiku): `lote` es lo enviado al especialista; con `huella_extracto`
    # (de `sanitizar`) en un esperado, su extracto tiene que ser el mismo.
    enviados, lote = None, p.get("lote")
    if lote is not None:
        try:
            if not isinstance(lote, dict):
                raise ValueError
            enviados = _indexar(lote.get("unidades"))
        except ValueError:
            return _error("lote_invalido")
        # Revisión Codex (PR #99): unidades de más esquivarían el tope del
        # plan y cambiarían el contexto del especialista.
        if set(enviados) != set(esperados):
            return _error("lote_distinto_de_esperados")
    resultados = []
    for ident, esperado in esperados.items():
        fila = filas.get(ident)
        motivo = "respuesta_ausente" if fila is None else _validar_fila(fila, criterios)
        control = esperado.get("control")
        # v3.21.22: `prioritario` (de coincidencias) activa el suelo; sin
        # él, una propuesta delegada podría quedar por debajo del suelo.
        permitidos = {"hard_rules", "extra_points", "forzar_reply_needed",
                      "tier_maximo", "remitente_en_historial",
                      "remitente_conteo_historial", "prioritario",
                      "remitente"}  # v3.21.27: el script decide prioritario
        if not isinstance(control, dict) or set(control) - permitidos:
            motivo = "control_invalido"
        elif not {"hard_rules", "extra_points", "forzar_reply_needed",
                  "tier_maximo", "remitente_en_historial"} <= set(control):
            motivo = "control_incompleto"
        elif (type(control["forzar_reply_needed"]) is not bool
              or type(control["remitente_en_historial"]) is not bool
              or type(control.get("prioritario", False)) is not bool
              or type(control.get("remitente", "")) is not str
              or not isinstance(control["hard_rules"], list)
              or not all(isinstance(k, str) for k in control["hard_rules"])
              or len(set(control["hard_rules"])) != len(control["hard_rules"])
              or type(control["extra_points"]) not in (int, float)
              or not math.isfinite(control["extra_points"])):
            motivo = "control_invalido"
        elif control["tier_maximo"] is not None:
            motivo = "cap_requiere_principal"
        huella = esperado.get("huella_extracto")
        if not motivo and huella is not None:
            enviado = (enviados or {}).get(ident)
            extracto = (enviado or {}).get("extracto")
            if (not isinstance(huella, str) or not isinstance(extracto, str)
                    or th.huella_extracto(extracto) != huella):
                motivo = "extracto_distinto"
        # v3.21.36 (prueba real 2026-10-24: extractos copiados a mano, con
        # texto ajeno, cortados o sin una línea): la huella mira el lote que
        # el principal declara; el eco, lo que el especialista recibió.
        ancla = esperado.get("ancla_extracto")
        if not motivo and ancla is not None:
            if not th.eco_coincide(fila.get("eco"), ancla):
                motivo = "eco_distinto"
        if motivo:
            resultados.append({"id": ident, "usar_principal": True, "motivo": motivo})
            continue
        entrada = dict(copy.deepcopy(control), id=ident, verdicts=fila["verdicts"])
        score = th.cmd_scoring_dispatch(entrada, cfg)
        if (score.get("ok") is False or score.get("ignorados") or "tier" not in score
                or type(score.get("score")) not in (int, float)
                or not math.isfinite(score["score"])):
            resultados.append({"id": ident, "usar_principal": True,
                               "motivo": "scoring_invalido"})
            continue
        umbrales = cfg.get("tiers", {})
        fronteras = [umbrales.get(k, v) for k, v in
                     (("reply_needed", 10), ("review", 4), ("reading_later", 0))]
        cerca = any(abs(score["score"] - v) <= 1 for v in fronteras)
        reevaluar = score["tier"] in ("ARCHIVE", "REPLY_NEEDED") or cerca
        motivo = "reevaluar_tier_o_umbral" if reevaluar else "propuesta_valida"
        # v3.21.26 (prueba real: Haiku anotó dudas en 5 de 5 y no quedó nada
        # que comparar): las dudas siguen sin autorizar nada (mismo motivo,
        # usar_principal), pero la propuesta se puntúa y viaja con ellas.
        if fila["dudas"]:
            reevaluar, motivo = True, "requiere_contexto_o_revision"
        fila_res = {"id": ident, "usar_principal": reevaluar, "motivo": motivo,
                    "payload_scoring": entrada, "resultado": score,
                    "evidencias": fila["evidencias"], "resumen": fila["resumen"],
                    "revision_obligatoria": True}
        if fila["dudas"]:
            fila_res["dudas"] = fila["dudas"]
        resultados.append(fila_res)
    salida = {"ok": True, "resultados": resultados}
    _frenar_plantillas(salida)
    return salida


def _frenar_plantillas(salida):
    """v3.21.7: el freno de plantilla de triage_helpers también para el lote
    delegado, que se puntúa correo a correo. Las propuestas con veredictos
    idénticos en bloque vuelven al principal. Jev guarda el score en
    `propuesta`; la delegación nativa, en `resultado`."""
    validas = [(r, r.get("resultado", r.get("propuesta")))
               for r in salida["resultados"] if "payload_scoring" in r]
    validas = [(r, sc) for r, sc in validas if isinstance(sc, dict)]
    alerta = th._alerta_plantilla([r["payload_scoring"] for r, _ in validas],
                                  [sc for _, sc in validas])
    if not alerta:
        return
    salida["alerta_plantilla"] = alerta
    for r, sc in validas:
        if sc.get("plantilla"):
            r.update(usar_principal=True, motivo="plantilla")


def comparar(p):
    """Compara propuestas, no verdad de referencia ni movimientos reales."""
    no_autorizada = _plan_autoriza(p)
    if no_autorizada:
        return no_autorizada
    return _comparar_filas(p)


def _comparar_filas(p):
    """Comparador puro, sin freno de delegación nativa.

    Lo usa la capa externa Jev (`jev.py`), que no pasa por `planificar`:
    su autorización es su propio opt-in (`config-jev.yaml`), no un plan.
    """
    base, propuesta = _indexar(p.get("base")), _indexar(p.get("propuesta"))
    if set(base) != set(propuesta):
        return _error("muestras_no_equivalentes")
    diferencias = []
    riesgo = []
    for ident, b in base.items():
        a = propuesta[ident]
        for fila in (b, a):
            if (not isinstance(fila.get("tier"), str)
                    or fila["tier"] not in th.TIER_ORDEN
                    or type(fila.get("score")) not in (int, float)
                    or not math.isfinite(fila["score"])):
                return _error("resultado_invalido")
        if b["tier"] != a["tier"] or b["score"] != a["score"]:
            diferencias.append({"id": ident, "tier_base": b["tier"],
                                "tier_propuesto": a["tier"],
                                "delta_score": a["score"] - b["score"]})
        if b["tier"] == "REPLY_NEEDED" and a["tier"] == "ARCHIVE":
            riesgo.append(ident)
    return {"ok": True, "total": len(base), "diferencias": diferencias,
            "reply_a_archive": riesgo, "referencia": "modelo_principal_no_verdad"}


def ejecutar(comando, payload):
    if not isinstance(payload, dict):
        return _error("entrada_no_es_objeto")
    try:
        return {"planificar": planificar, "validar": validar,
                "comparar": comparar}[comando](payload)
    except (ValueError, TypeError, KeyError, OverflowError):
        # No volcar valores del correo ni traceback al informar de errores.
        return _error("entrada_invalida")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("planificar")
    val = sub.add_parser("validar")
    val.add_argument("--config", help="Config YAML canónico; prevalece sobre el JSON")
    val.add_argument("--config-veloz", help="Capa veloz, solo con --config")
    # v3.21.31 (prueba real 2026-10-21: con ensayo_p3 activo, validar
    # comprobaba contra los criterios sin la capa y rechazaba a Haiku con
    # cobertura_incompleta). Mismo orden que scoring: veloz, luego ensayo.
    val.add_argument("--config-ensayo", help="Capa del ensayo P3, solo con --config")
    sub.add_parser("comparar")
    args = parser.parse_args()
    try:
        entrada = json.load(sys.stdin)
        if args.comando == "validar" and isinstance(entrada, dict):
            if (args.config_veloz or args.config_ensayo) and not args.config:
                raise ValueError("config_base_requerida")
            if args.config:
                # Reutiliza exactamente la carga/fusión del scoring existente.
                entrada["config"] = th._fusiona_config_ensayo(
                    th._fusiona_config_veloz(th._cargar_config(args.config),
                                             args.config_veloz),
                    args.config_ensayo)
        salida = ejecutar(args.comando, entrada)
    except (ValueError, UnicodeError, OSError, th.ConfigError, SystemExit):
        salida = _error("entrada_o_config_invalida")
    print(json.dumps(salida, ensure_ascii=False, allow_nan=False))
    return 0 if salida.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
