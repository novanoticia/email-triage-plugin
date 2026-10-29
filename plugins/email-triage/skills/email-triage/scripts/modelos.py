#!/usr/bin/env python3
"""Contratos locales para la delegación nativa opcional.

No invoca modelos, no accede a red/buzón y no escribe archivos. El host ejecuta
la delegación; este módulo comprueba elegibilidad, respuestas y comparaciones.
Solo LEE un fichero: el transcript del especialista que indique `validar`
(v3.22.9), para comprobar qué texto recibió de verdad.
Entrada y salida JSON por stdin/stdout, sin contenido de correos en argumentos.
"""
import argparse
import copy
import json
import math
import os
import re
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
    # v3.22.7 (prueba real 2026-10-26): Claude Code 2.1.310 cuenta la entrega
    # (`SubagentHandback`) como 1 acción y el principal omitió el campo para
    # que la respuesta contara: la omisión dejaba el freno abierto. Ahora es
    # obligatorio; `herramientas_especialista` (nombres del host) exime solo
    # la entrega, y un host que no lo informe se declara con "no_informado".
    verificadas, motivo = _herramientas_especialista(p)
    if motivo:
        return _error(motivo)
    cfg = p.get("config")
    if not isinstance(cfg, dict):
        return _error("config_invalida")
    criterios = _criterios(cfg)
    esperados = _indexar(p.get("esperados"))
    # v3.22.24 (prueba real 2026-10-28: el especialista no entregó y el
    # principal sacó el JSON de su transcript con un script propio): con
    # transcript, la respuesta es la que el especialista ESCRIBIÓ. Sin
    # `respuesta`, `validar` la toma de ahí; con ella, cada fila tiene que
    # ser la emitida (`respuesta_distinta`): retocar veredictos ya no pasa.
    leido = emitida = None
    if "transcript_especialista" in p:
        leido, motivo_transcript = _texto_recibido(p["transcript_especialista"])
        if motivo_transcript:
            return _error(motivo_transcript)
        emitida = leido[2]
        if emitida is None:
            return _error("respuesta_no_emitida")
    respuesta = p.get("respuesta", _ids_como_texto(emitida))
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
    # v3.22.9 (prueba real 2026-10-26: el principal alteró al copiarlos 4 de
    # 41 extractos y ni la huella ni el eco lo vieron): con el transcript del
    # host se comprueba, extracto a extracto, que el especialista recibió el
    # texto completo. Opcional: solo existe donde el host guarda transcript.
    recibido = None
    if "transcript_especialista" in p:
        if enviados is None:
            return _error("transcript_sin_lote")
        recibido, usadas, _ = leido
        # Lo que dice el transcript manda sobre lo que copia el principal:
        # el freno de herramientas ya no depende de `acciones_especialista`.
        motivo = _herramientas_transcript(usadas, p["acciones_especialista"])
        if motivo:
            return _error(motivo)
        verificadas = True
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
        if not motivo and recibido is not None:
            if not _entregado((enviados.get(ident) or {}).get("extracto"), recibido,
                              ident):
                motivo = "entrega_distinta"
        if not motivo and emitida is not None and not _fila_emitida(fila, emitida, ident):
            motivo = "respuesta_distinta"
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
    salida = {"ok": True, "resultados": resultados,
              "herramientas_verificadas": verificadas,
              "entrega_verificada": recibido is not None}
    if recibido is not None:
        salida["herramientas_en_transcript"] = usadas
        salida["respuesta_desde_transcript"] = "respuesta" not in p
    _frenar_plantillas(salida)
    return salida


ENTREGA_ESPECIALISTA = "SubagentHandback"
MAX_TRANSCRIPT = 50 * 1024 * 1024
_MARCA_TRUNCADO = re.compile(r"\s*\[truncado\]\s*$")


def _sin_espacios(texto):
    """Espacios, tabuladores y saltos colapsados: el host o el principal
    pueden reflujar líneas sin cambiar el contenido (14 de 41 en la prueba)."""
    return re.sub(r"\s+", " ", texto).strip()


def _texto_recibido(ruta):
    """(({id: extractos recibidos}, [herramientas usadas], respuesta | None),
    motivo | None).

    Lee el transcript JSONL del host (formato de Claude Code: entradas
    `type: user` con `message.content` en texto o en bloques `text`) y une
    lo que recibió el especialista (ver `_entregas`). De las entradas
    `type: assistant` (y `user`) toma los bloques `*tool_use` (sus nombres,
    una vez por id) y cuenta como «desconocida» cada `tool_result` sin su
    `tool_use`: lo que el especialista hizo, no lo que el principal copia.
    v3.22.24: también la última respuesta que ESCRIBIÓ (el texto de sus
    entradas `assistant` o la entrada de su `SubagentHandback`), o None.
    Solo lee. Un fichero sin ese texto es
    `transcript_no_reconocido`: nunca un «todo bien» por defecto."""
    if not _texto(ruta):
        return None, "transcript_invalido"
    ruta = os.path.expanduser(ruta)
    try:
        if not os.path.isfile(ruta) or os.path.getsize(ruta) > MAX_TRANSCRIPT:
            return None, "transcript_ilegible"
        partes, usadas, ids_uso, ids_resultado, emitido = [], [], set(), set(), []
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    doc = json.loads(ln)
                except ValueError:
                    continue
                if not isinstance(doc, dict) or doc.get("type") not in ("user", "assistant"):
                    continue
                mensaje = doc.get("message")
                contenido = mensaje.get("content") if isinstance(mensaje, dict) else None
                # Revisión Mistral (PR #127): cualquier entrada, no solo
                # `assistant`; y un `tool_result` sin su `tool_use` también
                # prueba que corrió una herramienta (fail-closed).
                for b in contenido if isinstance(contenido, list) else ():
                    tipo = b.get("type") if isinstance(b, dict) else None
                    if not isinstance(tipo, str):
                        continue
                    if tipo.endswith("tool_use"):
                        ident = b.get("id")
                        if isinstance(ident, str) and ident in ids_uso:
                            continue
                        ids_uso.add(ident)
                        usadas.append(b["name"] if _texto(b.get("name")) else "desconocida")
                        if doc["type"] == "assistant" and b.get("name") == ENTREGA_ESPECIALISTA:
                            emitido.append(b.get("input"))
                    elif tipo == "text" and doc["type"] == "assistant":
                        emitido.append(b.get("text"))
                    elif tipo.endswith("tool_result"):
                        ids_resultado.add(b.get("tool_use_id"))
                if doc["type"] == "assistant":
                    if isinstance(contenido, str):
                        emitido.append(contenido)
                    continue
                if isinstance(contenido, str):
                    partes.append(contenido)
                elif isinstance(contenido, list):
                    partes.extend(b["text"] for b in contenido if isinstance(b, dict)
                                  and b.get("type") == "text" and isinstance(b.get("text"), str))
    except OSError:
        return None, "transcript_ilegible"
    usadas += ["desconocida"] * len(ids_resultado - ids_uso)
    crudo = "\n".join(partes)
    if not _sin_espacios(crudo):
        return None, "transcript_no_reconocido"
    return (_entregas(crudo), usadas, _ultima_respuesta(emitido)), None


def _es_respuesta(v):
    return isinstance(v, dict) and set(v) == {"evaluaciones"}


def _ultima_respuesta(emitido):
    """La última `{"evaluaciones": …}` que escribió el especialista, o None.

    Busca en su texto (también dentro de un bloque ```json) y en la entrada
    de su `SubagentHandback`, en orden: si corrigió la respuesta, vale la
    última; un JSON de ejemplo anterior tampoco estorba."""
    ultima, decodificador = None, json.JSONDecoder()
    pendientes = list(reversed(emitido))
    while pendientes:
        v = pendientes.pop()
        if _es_respuesta(v):
            ultima = v
        elif isinstance(v, dict):
            pendientes.extend(reversed(list(v.values())))
        elif isinstance(v, list):
            pendientes.extend(reversed(v))
        elif isinstance(v, str):
            i = v.find("{")
            while i != -1:
                try:
                    valor, fin = decodificador.raw_decode(v, i)
                except ValueError:
                    i = v.find("{", i + 1)
                    continue
                if _es_respuesta(valor):
                    ultima = valor
                i = v.find("{", fin)
    return ultima


def _ids_como_texto(emitida):
    """Copia de `emitida` con los ids numéricos como texto, igual que los
    acepta `_fila_emitida` (revisión Codex P2, PR #143: con `"id": 1`,
    omitir `respuesta` daba `entrada_invalida` y copiarla, no). Los
    duplicados siguen llegando a `_indexar`."""
    if not _es_respuesta(emitida) or not isinstance(emitida["evaluaciones"], list):
        return emitida
    return {"evaluaciones": [
        dict(f, id=str(f["id"])) if isinstance(f, dict) and type(f.get("id")) is int else f
        for f in emitida["evaluaciones"]]}


def _fila_emitida(fila, emitida, ident):
    """True si `fila` es, campo a campo, la única que el especialista
    escribió bajo `ident` (su id puede venir como número). Dos filas con el
    mismo id en lo emitido no prueban cuál vale: False."""
    filas = emitida.get("evaluaciones")
    propias = [f for f in filas if isinstance(f, dict)
               and type(f.get("id")) in (str, int) and str(f["id"]) == ident
               ] if isinstance(filas, list) else []
    if len(propias) != 1:
        return False
    return ({k: v for k, v in propias[0].items() if k != "id"}
            == {k: v for k, v in fila.items() if k != "id"})


_ETIQUETA = re.compile(r'<email-body-data\s+id\s*=\s*"([^"<>]*)"\s*>(.*?)</email-body-data>',
                       re.DOTALL)


def _entregas(crudo):
    """{id: [extractos recibidos, normalizados]} de las dos formas con
    estructura: `<email-body-data id="8">…</email-body-data>` o un JSON con
    `{"id": "8", "extracto": …}` (p. ej. el lote tal cual).

    Revisión Codex P2 ×3 (PR #126): buscar el extracto como subcadena del
    texto libre aceptaba añadidos antes o después («… Urgente.»), tomaba un
    «ID 2» del asunto por una marca de unidad y no unía los pares
    sustitutos de `\\ud83d\\udcca`. Ahora el id es un campo y el extracto se
    compara entero; el JSON lo descodifica `json`, no una regex."""
    vistos = {}

    def anotar(ident, extracto):
        if type(ident) is int:
            ident = str(ident)
        if isinstance(ident, str) and isinstance(extracto, str):
            vistos.setdefault(ident, []).append(_normalizar_extracto(extracto))

    for m in _ETIQUETA.finditer(crudo):
        anotar(m.group(1), m.group(2))
    # Revisión Codex P2 (PR #126): un JSON de ejemplo dentro del correo es
    # dato, no una entrega; el barrido JSON no mira dentro de las etiquetas.
    crudo = _ETIQUETA.sub(" ", crudo)
    decodificador = json.JSONDecoder()
    i = crudo.find("{")
    while i != -1:
        try:
            valor, fin = decodificador.raw_decode(crudo, i)
        except ValueError:
            i = crudo.find("{", i + 1)
            continue
        pendientes = [valor]
        while pendientes:
            v = pendientes.pop()
            if isinstance(v, dict):
                if "id" in v and "extracto" in v:
                    anotar(v["id"], v["extracto"])
                pendientes.extend(v.values())
            elif isinstance(v, list):
                pendientes.extend(v)
        i = crudo.find("{", fin)
    return vistos


def _normalizar_extracto(texto):
    return _sin_espacios(_MARCA_TRUNCADO.sub("", texto))


def _entregado(extracto, entregas, ident):
    """True si el especialista recibió bajo `ident` el extracto entero (salvo
    espacios y la marca final « [truncado]») y nada distinto bajo ese id.
    Sin una entrega con estructura para la unidad, `entrega_distinta`: lo
    seguro (así tampoco pasan dos extractos intercambiados entre correos)."""
    if not isinstance(extracto, str) or not _texto(ident):
        return False
    recibidos = entregas.get(ident)
    base = _normalizar_extracto(extracto)
    return bool(recibidos) and all(r == base for r in recibidos)


def _herramientas_especialista(p):
    """(verificadas, motivo de error | None) a partir de lo que informa el host.

    `acciones_especialista`: el `tool_uses` del host (int >= 0) o
    "no_informado" si el host no lo da. `herramientas_especialista`
    (opcional, solo con int): los nombres, tantos como acciones. Solo una
    `SubagentHandback` se descuenta; cualquier otra acción es herramienta.
    """
    if "acciones_especialista" not in p:
        return False, "acciones_especialista_ausente"
    acciones = p["acciones_especialista"]
    nombres = p.get("herramientas_especialista")
    if acciones == "no_informado":
        if "herramientas_especialista" in p:
            return False, "herramientas_especialista_invalidas"
        return False, None
    if type(acciones) is not int or acciones < 0:
        return False, "acciones_especialista_invalidas"
    entregas = 0
    if "herramientas_especialista" in p:
        if (not isinstance(nombres, list) or len(nombres) != acciones
                or not all(_texto(n) for n in nombres)):
            return False, "herramientas_especialista_invalidas"
        if any(n != ENTREGA_ESPECIALISTA for n in nombres) or len(nombres) > 1:
            return False, "especialista_uso_herramientas"
        entregas = len(nombres)
    if acciones - entregas > 0:
        return False, "especialista_uso_herramientas"
    return True, None


def _herramientas_transcript(usadas, acciones):
    """Motivo de error | None según las herramientas del transcript.

    Como en `_herramientas_especialista`, solo una `SubagentHandback` se
    descuenta. Si el principal declaró menos acciones de las que el
    transcript muestra, copió mal o las ocultó: `acciones_no_coinciden`.
    "no_informado" no se contrasta (el host no dio el dato); el transcript
    lo suple."""
    otras = [n for n in usadas if n != ENTREGA_ESPECIALISTA]
    if otras or len(usadas) > 1:
        return "especialista_uso_herramientas"
    if type(acciones) is int and acciones < len(usadas):
        return "acciones_no_coinciden"
    return None


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
