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
    if not isinstance(cfg, dict):
        return _error("config_modelos_invalida")
    modo = cfg.get("modo", "actual")
    if modo == "actual":
        return {"ok": True, "modo": "actual", "delegar": False}
    if modo not in ("comparar", "hibrido"):
        return _error("modo_no_admitido")
    if set(cfg) - {"modo", "modelo", "max_llamadas", "tamano_lote"}:
        return _error("opcion_no_admitida")
    limite = cfg.get("max_llamadas", 2)
    lote = cfg.get("tamano_lote", 25)
    usadas = p.get("llamadas_realizadas", 0)
    if not (_entero(limite, 1, 10) and _entero(lote, 1, 50)
            and _entero(usadas, 0, 1000)):
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
    if proveedor not in ("anthropic", "openai"):
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
    return {"ok": True, "modo": modo, "delegar": True,
            "modelo_solicitado": modelo, "proveedor": proveedor,
            "llamadas_restantes": limite - usadas, "tamano_lote": lote,
            "concurrencia": 1}


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
            or plan.get("modo") not in ("comparar", "hibrido")):
        return _error("delegacion_no_autorizada")
    return None


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
    if set(fila) != campos:
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
    if fila["dudas"]:
        return "requiere_contexto_o_revision"
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
    resultados = []
    for ident, esperado in esperados.items():
        fila = filas.get(ident)
        motivo = "respuesta_ausente" if fila is None else _validar_fila(fila, criterios)
        control = esperado.get("control")
        permitidos = {"hard_rules", "extra_points", "forzar_reply_needed",
                      "tier_maximo", "remitente_en_historial",
                      "remitente_conteo_historial"}
        if not isinstance(control, dict) or set(control) - permitidos:
            motivo = "control_invalido"
        elif not {"hard_rules", "extra_points", "forzar_reply_needed",
                  "tier_maximo", "remitente_en_historial"} <= set(control):
            motivo = "control_incompleto"
        elif (type(control["forzar_reply_needed"]) is not bool
              or type(control["remitente_en_historial"]) is not bool
              or not isinstance(control["hard_rules"], list)
              or not all(isinstance(k, str) for k in control["hard_rules"])
              or len(set(control["hard_rules"])) != len(control["hard_rules"])
              or type(control["extra_points"]) not in (int, float)
              or not math.isfinite(control["extra_points"])):
            motivo = "control_invalido"
        elif control["tier_maximo"] is not None:
            motivo = "cap_requiere_principal"
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
        resultados.append({"id": ident, "usar_principal": reevaluar,
                           "motivo": "reevaluar_tier_o_umbral" if reevaluar else "propuesta_valida",
                           "payload_scoring": entrada, "resultado": score,
                           "evidencias": fila["evidencias"], "resumen": fila["resumen"],
                           "revision_obligatoria": True})
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
    sub.add_parser("comparar")
    args = parser.parse_args()
    try:
        entrada = json.load(sys.stdin)
        if args.comando == "validar" and isinstance(entrada, dict):
            if args.config_veloz and not args.config:
                raise ValueError("config_base_requerida")
            if args.config:
                # Reutiliza exactamente la carga/fusión del scoring existente.
                entrada["config"] = th._fusiona_config_veloz(
                    th._cargar_config(args.config), args.config_veloz)
        salida = ejecutar(args.comando, entrada)
    except (ValueError, UnicodeError, OSError, th.ConfigError, SystemExit):
        salida = _error("entrada_o_config_invalida")
    print(json.dumps(salida, ensure_ascii=False, allow_nan=False))
    return 0 if salida.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
