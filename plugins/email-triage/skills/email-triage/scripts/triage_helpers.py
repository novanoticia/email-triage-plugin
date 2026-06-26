#!/usr/bin/env python3
"""triage_helpers.py — Lógica determinista del plugin email-triage (v3.7).

Extrae a código las partes del SKILL.md que no deben depender de la
aritmética mental del modelo:

  ajustes         PASO 0.B — decay temporal y agregación de correcciones.jsonl
  sanitizar       Pipeline S0–S5 — limpieza del cuerpo ANTES de exponerlo al modelo
  scoring         PASO 4 — agregación determinista de veredictos (single o lote)
  validar-config  PASO 0 — parseo/validación del YAML antes de operar

Novedades v3.7 (parche de 5 prioridades sobre el scoring determinista de v3.6):
  1. scoring capa REPLY_NEEDED→REVIEW cuando presion_accion<=0 (salvo
     forzar_reply_needed). "Muy valioso para leer" != "exige respuesta".
  2. scoring atenúa sender_bulk_penalizacion cuando remitente_en_historial:
     un remitente que el usuario conserva no recibe el castigo completo.
  3. scoring acepta lote {"emails":[...]} y flag --brief (solo score/tier/ejes):
     1 parse de YAML + salida compacta = mucho menos tiempo y tokens.
  4. nuevo subcomando validar-config: parsea el YAML y reporta ok/error+línea.

Uso:
  python3 triage_helpers.py ajustes [--correcciones RUTA]
  python3 triage_helpers.py sanitizar [--archivo RUTA] [--max-chars 1500] [--asunto TXT]
                            (sin --archivo lee de stdin)
  python3 triage_helpers.py scoring [--config RUTA] [--brief]
                            (lee payload JSON de stdin; single o {"emails":[...]})
  python3 triage_helpers.py validar-config [--config RUTA]

Salida: JSON por stdout. Solo stdlib salvo PyYAML (scoring/validar-config).
Sin efectos laterales: este script NUNCA escribe ficheros ni mueve correos.
"""
import argparse
import html as html_mod
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

TIER_ORDEN = {"ARCHIVE": 0, "READING_LATER": 1, "REVIEW": 2, "REPLY_NEEDED": 3}

STOPWORDS = {
    "de", "la", "el", "los", "las", "un", "una", "y", "o", "en", "del",
    "para", "por", "con", "sin", "que", "tu", "su", "al", "se", "es",
    "the", "a", "an", "and", "or", "in", "of", "for", "to", "your",
    "on", "at", "is", "are", "re", "fwd", "fw", "rv",
}


# ════════════════════════════════════════════════════════════════
# PASO 0.B — ajustes aprendidos
# ════════════════════════════════════════════════════════════════

def _parse_ts(ts_iso):
    """Datetime tz-aware desde ISO-8601 (acepta sufijo Z), o None."""
    try:
        ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError, TypeError):
        return None


def _decay(ts_iso, ahora):
    """×1.0 (<=30 días), ×0.5 (31-90), None (>90 o fecha ilegible)."""
    ts = _parse_ts(ts_iso)
    if ts is None:
        return None
    dias = (ahora - ts).days
    if dias < 0:
        return None
    if dias <= 30:
        return 1.0
    if dias <= 90:
        return 0.5
    return None


def _umbral(suma, fuerte, debil, tope):
    """Mapea una suma ponderada a un ajuste según los umbrales del SKILL.md."""
    if suma >= fuerte:
        return min(3, tope)
    if suma >= debil:
        return min(2, tope)
    if suma <= -fuerte:
        return -min(3, tope)
    if suma <= -debil:
        return -min(2, tope)
    return 0


def cmd_ajustes(ruta: str) -> dict:
    ahora = datetime.now(timezone.utc)
    entradas = []
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    entradas.append(json.loads(linea))
                except json.JSONDecodeError:
                    continue
    usadas, por_remitente, por_dominio = [], defaultdict(float), defaultdict(float)
    kw_peso, kw_count_up, kw_count_down = (defaultdict(float), defaultdict(int),
                                           defaultdict(int))
    for e in entradas:
        peso = _decay(e.get("ts", ""), ahora)
        ta, tc = e.get("tier_asignado"), e.get("tier_corregido")
        if peso is None or ta not in TIER_ORDEN or tc not in TIER_ORDEN:
            continue
        if e.get("simulacion"):
            # Correcciones hechas durante un dry-run: a menudo se producen
            # probando pesos o umbrales experimentales, así que aprenden
            # a medio peso para no contaminar el perfil de producción.
            peso *= 0.5
        direccion = TIER_ORDEN[tc] - TIER_ORDEN[ta]
        if direccion == 0:
            continue
        ponderada = direccion * peso
        usadas.append({"ts_dt": _parse_ts(e.get("ts", "")),
                       "direccion": direccion, "peso": peso})
        remitente = (e.get("from") or "").strip().lower()
        if remitente:
            por_remitente[remitente] += ponderada
            if "@" in remitente:
                por_dominio["@" + remitente.split("@", 1)[1]] += ponderada
        for palabra in re.findall(r"[a-záéíóúüñ0-9]{3,}",
                                  (e.get("subject") or "").lower()):
            if palabra in STOPWORDS:
                continue
            kw_peso[palabra] += ponderada
            if direccion > 0:
                kw_count_up[palabra] += 1
            else:
                kw_count_down[palabra] += 1

    aj_rem = {r: a for r, s in por_remitente.items()
              if (a := _umbral(s, 5, 3, 3)) != 0}
    aj_dom = {d: (1 if s >= 6 else -1) for d, s in por_dominio.items()
              if s >= 6 or s <= -6}
    aj_kw = {}
    for k, s in kw_peso.items():
        if kw_count_up[k] >= 3 and s >= 3:
            aj_kw[k] = 1
        elif kw_count_down[k] >= 3 and s <= -3:
            aj_kw[k] = -1
    deriva = None
    # orden cronológico real: con zonas horarias mixtas, el orden
    # lexicográfico del string ISO no es cronológico (3.10b)
    ultimas = sorted(usadas, key=lambda x: x["ts_dt"])[-20:]
    if len(ultimas) >= 10:
        arriba = sum(1 for u in ultimas if u["direccion"] > 0)
        pct = arriba / len(ultimas)
        if pct > 0.70:
            deriva = {"sentido": "sube", "porcentaje": round(pct * 100),
                      "sugerencia": "Considera bajar tiers.review en config.yaml"}
        elif pct < 0.30:
            deriva = {"sentido": "baja", "porcentaje": round((1 - pct) * 100),
                      "sugerencia": "Considera subir tiers.review en config.yaml"}
    return {
        "correcciones_totales": len(entradas),
        "correcciones_usadas": len(usadas),
        "ajustes_remitente": aj_rem,
        "ajustes_dominio": aj_dom,
        "ajustes_keyword": aj_kw,
        "deriva": deriva,
    }


# ════════════════════════════════════════════════════════════════
# Pipeline S0–S5 — sanitización del cuerpo
# ════════════════════════════════════════════════════════════════

_CTX_INSTR = r"(instruc\w+|instruction\w*|prompt\w*|previous|anterior\w*|reglas?|rules?|system)"
_ROL_IA = (r"(assistant|asistente|ai|llm|chatbot|model\w*|"
           r"clasificador\w*|classifier|agente?s?|skill)")
_TIER = r"(reply[_ ]?needed|review|reading[_ ]?later|archive)"

S0_PATRONES = [
    ("ignorar_instrucciones",
     re.compile(r"\b(ignore|forget|disregard|override|ignora|olvida|descarta)\b"
                r".{0,40}\b" + _CTX_INSTR + r"\b", re.I | re.S)),
    ("rol_sistema",
     re.compile(r"(?:\byou are\b(?! receiving| subscrib)|\beres\b|"
                r"\bact as\b|\bact[uú]a como\b).{0,40}?\b" + _ROL_IA + r"\b"
                r"|^\s*system:|^\s*assistant:|<system>|\[INST\]|### ?Instruction",
                re.I | re.M | re.S)),
    ("escape_delimitador",
     re.compile(r"</?email-body-data>|---EMAIL|^tier:\s*" + _TIER,
                re.I | re.M)),
    ("comando_directo",
     re.compile(r"\bmark (?:this|it)\b.{0,15}\bas\b.{0,15}" + _TIER +
                r"|\bmove (?:this|it)\b.{0,25}\b(?:folder|inbox|" + _TIER + r")\b"
                r"|\brate this (?:email|message|correo|mensaje)\b"
                r"|\bm[aá]rcalo como\b.{0,15}\b(?:urgente|" + _TIER + r")\b"
                r"|\bmu[eé]velo a\b.{0,25}\b(?:carpeta|bandeja|inbox|urgentes|"
                + _TIER + r")\b"
                r"|\bdale un score de\b", re.I)),
]

S1_CORTES = [
    re.compile(r"^On .{1,120} wrote:", re.M),
    re.compile(r"^El .{1,120} escribi[oó]:", re.M),
    re.compile(r"^-{5,} ?Forwarded message ?-{5,}", re.M | re.I),
    re.compile(r"(?:^> .*\n){3,}", re.M),
    re.compile(r"^From: .*@", re.M),
    re.compile(r"^_{5,}\s*$", re.M),
]

S4_CORTES = [
    re.compile(r"^--\s*$", re.M),
    re.compile(r"(Enviado desde mi|Sent from my) ", re.I),
    re.compile(r"(Este (mensaje|correo) (es|y sus adjuntos)|"
               r"This (e-?mail|message) (is|and its attach))", re.I),
]


def _primer_corte(texto, patrones):
    pos = len(texto)
    for pat in patrones:
        m = pat.search(texto)
        if m and m.start() < pos:
            pos = m.start()
    return texto[:pos]


def _vista_decodificada(texto):
    """Vista solo-para-detección: entidades HTML decodificadas y tags
    eliminados. Caza payloads ofuscados (&#105;gnore, ig<b>nore</b>)."""
    return re.sub(r"<[^>]+>", "", html_mod.unescape(texto))


def _detectar_s0(texto):
    """Patrones S0 sobre el texto crudo y su vista decodificada."""
    vistas = (texto, _vista_decodificada(texto))
    return sorted({nombre for nombre, pat in S0_PATRONES
                   for v in vistas if pat.search(v)})


def cmd_sanitizar(texto: str, max_chars: int = 1500,
                  asunto: Optional[str] = None) -> dict:
    # Guarda contra max_chars no positivo (config o --max-chars mal puestos):
    # texto[:0] vaciaria el cuerpo y texto[:-n] lo cortaria por el final. Ante
    # un valor invalido se cae al presupuesto por defecto documentado (1500).
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) \
            or max_chars <= 0:
        max_chars = 1500
    original = len(texto)
    flags = _detectar_s0(texto)                       # S0 en doble vista
    injection_cuerpo = bool(flags)

    flags_asunto = _detectar_s0(asunto) if asunto else []
    injection_asunto = bool(flags_asunto)
    injection = injection_cuerpo or injection_asunto

    base64_block = re.search(
        r"(?:^[A-Za-z0-9+/=]{76,}\s*$\n?){2,}|^[A-Za-z0-9+/=]{200,}\s*$",
        texto, re.M)

    texto = _primer_corte(texto, S1_CORTES)                       # S1
    html_detectado = bool(re.search(
        r"<(div|table|span|style|head|html|body|p|br|td)\b|<!DOCTYPE", texto, re.I))
    if html_detectado:                                            # S2
        texto = re.sub(r"<(style|script)\b.*?</\1>", " ", texto, flags=re.I | re.S)
        texto = re.sub(r"<[^>]+>", " ", texto)
        texto = html_mod.unescape(texto)
    texto = _primer_corte(texto, S4_CORTES)                       # S4
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto).strip()

    truncado = False                                              # S5
    if len(texto) > max_chars:
        texto, truncado = texto[:max_chars], True
    utiles = len(texto.strip())
    especiales = sum(1 for c in texto if not (c.isalnum() or c.isspace()))
    ratio = (especiales / len(texto)) if texto else 0.0

    if injection:
        etiqueta, texto = "[⚠️ posible inyección detectada]", ""
    elif base64_block:
        etiqueta, texto = "[contenido codificado Base64]", ""
    elif utiles < 30:
        etiqueta = ("[cuerpo no legible — HTML sin texto plano]"
                    if html_detectado else "[cuerpo no legible]")
        texto = ""
    elif ratio > 0.40:
        etiqueta, texto = "[cuerpo corrupto]", ""
    elif html_detectado:
        etiqueta = "[HTML detectado]"
    else:
        etiqueta = "[texto limpio]"
    return {
        "etiqueta": etiqueta,
        "texto": texto + (" [truncado]" if truncado and texto else ""),
        "injection": injection,
        "injection_cuerpo": injection_cuerpo,
        "injection_asunto": injection_asunto if asunto is not None else None,
        "patrones_detectados": flags,
        "patrones_asunto": flags_asunto,
        "asunto_evaluable": (("" if injection_asunto else asunto)
                             if asunto is not None else None),
        "tier_maximo": "REVIEW" if injection else None,
        "ajuste_score": -3 if injection else 0,
        "longitud_original": original,
        "longitud_final": len(texto),
    }


# ════════════════════════════════════════════════════════════════
# PASO 4 — scoring determinista (single o lote, opcionalmente brief)
# ════════════════════════════════════════════════════════════════

EJES_DEFAULT = {
    "valor_decisional": [0, 10],
    "calidad_epistemica": [-10, 10],
    "riesgo_manipulacion": [-10, 0],
    "coste_cognitivo": [-5, 0],
    "presion_accion": [0, 10],
}
_META_CRIT = {"activo", "core", "weight", "question", "eje"}


def _tier_por_score(score, tiers):
    if score >= tiers.get("reply_needed", 10):
        return "REPLY_NEEDED"
    if score >= tiers.get("review", 4):
        return "REVIEW"
    if score >= tiers.get("reading_later", 0):
        return "READING_LATER"
    return "ARCHIVE"


def _aplica_hard_rules(hard_rules, hard_cfg, en_historial, atenuado_a, ignorados):
    """Suma las hard rules. Atenúa sender_bulk_penalizacion cuando el
    remitente está en el historial de conservados (corrección #2): un
    remitente que el usuario guarda a mano no merece el castigo completo
    de 'remitente masivo'."""
    hard_puntos, hard_desglose = 0, []
    for k in (hard_rules or []):
        v = hard_cfg.get(k)
        if v is None:
            ignorados.append({"hard_rule": k, "motivo": "no definida en config"})
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            ignorados.append({"hard_rule": k,
                              "motivo": "valor no numerico en config (%r)" % (v,)})
            continue
        nota = None
        if k == "sender_bulk_penalizacion" and en_historial and v < 0:
            nuevo = max(v, atenuado_a)
            if nuevo != v:
                nota = "atenuada por remitente_en_historial (%d->%d)" % (v, nuevo)
                v = nuevo
        hard_puntos += v
        entry = {"regla": k, "puntos": v}
        if nota:
            entry["nota"] = nota
        hard_desglose.append(entry)
    return hard_puntos, hard_desglose


def cmd_scoring(payload: dict, cfg: dict) -> dict:
    """Agrega veredictos del modelo en un score+tier deterministas.

    payload: {"verdicts": {criterio: valor}, "hard_rules": [clave...],
              "extra_points": int, "forzar_reply_needed": bool,
              "tier_maximo": "REVIEW"|None,
              "remitente_en_historial": bool,   # corrección #2
              "id": cualquier}                   # opcional, para lote
    cfg: config.yaml ya parseado (dict). Devuelve score, tier, ejes y desglose.
    """
    criterios = cfg.get("criterios_epistemicos", {}) or {}
    scfg = cfg.get("scoring", {}) or {}
    rangos = scfg.get("ejes", EJES_DEFAULT)
    tiers = cfg.get("tiers", {}) or {}
    hard_cfg = cfg.get("hard_rules", {}) or {}
    # Parámetros configurables del parche (con defaults seguros):
    cap_no_accion = scfg.get("cap_reply_needed_sin_accion", True)
    bulk_atenuado_a = scfg.get("sender_bulk_atenuado_a", -1)

    ejes = {nombre: 0 for nombre in rangos}
    desglose, ignorados = [], []

    for crit, verdict in (payload.get("verdicts") or {}).items():
        c = criterios.get(crit)
        if not c or not c.get("activo", True):
            ignorados.append({"criterio": crit, "motivo": "desconocido o inactivo"})
            continue
        eje = c.get("eje")
        valores = {k: v for k, v in c.items() if k not in _META_CRIT}
        if verdict not in valores:
            ignorados.append({"criterio": crit,
                              "motivo": "veredicto '%s' no valido; opciones: %s"
                              % (verdict, sorted(valores))})
            continue
        if eje not in ejes:
            ignorados.append({"criterio": crit,
                              "motivo": "sin eje valido (eje=%r)" % eje})
            continue
        pts = valores[verdict]
        ejes[eje] += pts
        desglose.append({"criterio": crit, "veredicto": verdict,
                         "eje": eje, "puntos": pts})

    ejes_clamp = {}
    for nombre, val in ejes.items():
        lo, hi = rangos[nombre]
        ejes_clamp[nombre] = max(lo, min(hi, val))

    en_historial = bool(payload.get("remitente_en_historial"))
    hard_puntos, hard_desglose = _aplica_hard_rules(
        payload.get("hard_rules"), hard_cfg, en_historial, bulk_atenuado_a, ignorados)

    extra = payload.get("extra_points", 0) or 0
    score = sum(ejes_clamp.values()) + hard_puntos + extra

    tier = _tier_por_score(score, tiers)
    cap_aplicado = None
    if payload.get("forzar_reply_needed"):
        tier = "REPLY_NEEDED"
    elif cap_no_accion and tier == "REPLY_NEEDED":
        # Corrección #1: REPLY_NEEDED = "exige TU respuesta/acción". La
        # única señal fiable de eso es forzar_reply_needed (pregunta
        # directa, deadline <=72h, hilo bloqueado) que fija el SKILL.
        # Score, urgencia e impacto_causal_real miden importancia, no
        # "necesita réplica": por sí solos llegan como mucho a REVIEW.
        # (presion_accion NO sirve de gate: impacto_causal_real se le
        # suma, y un correo puede tener impacto sin pedir respuesta.)
        cap_aplicado = "REPLY_NEEDED->REVIEW (sin señal de acción explícita)"
        tier = "REVIEW"

    # Cap por inyección (v3.5): nunca por encima de tier_maximo.
    tmax = payload.get("tier_maximo")
    if tmax in TIER_ORDEN and TIER_ORDEN[tier] > TIER_ORDEN[tmax]:
        tier = tmax

    out = {
        "modo": "determinista",
        "score": score,
        "tier": tier,
        "ejes": ejes_clamp,
        "ejes_sin_clampar": ejes,
        "hard_rules": hard_desglose,
        "hard_puntos": hard_puntos,
        "extra_points": extra,
        "remitente_en_historial": en_historial,
        "criterios": desglose,
        "ignorados": ignorados,
    }
    if cap_aplicado:
        out["cap_aplicado"] = cap_aplicado
    if "id" in payload:
        out["id"] = payload["id"]
    return out


def _brief(r):
    """Vista compacta para ahorrar tokens: solo lo accionable."""
    out = {"score": r["score"], "tier": r["tier"], "ejes": r["ejes"]}
    if r.get("cap_aplicado"):
        out["cap_aplicado"] = r["cap_aplicado"]
    if r.get("ignorados"):
        out["ignorados"] = r["ignorados"]
    if "id" in r:
        out["id"] = r["id"]
    return out


def cmd_scoring_dispatch(payload: dict, cfg: dict, brief: bool = False) -> dict:
    """single o lote. Lote: {"emails":[{id, verdicts, ...}, ...]}."""
    if isinstance(payload.get("emails"), list):
        res = [cmd_scoring(item, cfg) for item in payload["emails"]]
        return {"resultados": [_brief(r) if brief else r for r in res]}
    r = cmd_scoring(payload, cfg)
    return _brief(r) if brief else r


# ════════════════════════════════════════════════════════════════
# PASO 0 — validación del config YAML
# ════════════════════════════════════════════════════════════════

def cmd_validar_config(ruta: str) -> dict:
    """Parsea el YAML y reporta ok/error+línea para que el SKILL pueda
    abortar con un mensaje claro (y ofrecer autofix) antes de operar."""
    try:
        import yaml
    except ImportError:
        return {"ok": False, "error": "PyYAML no instalado",
                "remedio": "pip install pyyaml --break-system-packages"}
    if not os.path.exists(ruta):
        return {"ok": False, "error": "no existe: %s" % ruta}
    try:
        with open(ruta, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as e:
        info = {"ok": False, "error": str(e).splitlines()[0]}
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            info["linea"] = mark.line + 1
            info["columna"] = mark.column + 1
        return info
    if not isinstance(data, dict):
        return {"ok": False, "error": "el YAML no es un mapeo de claves"}
    recomendados = ("usuario", "correo", "carpetas", "tiers",
                    "criterios_epistemicos")
    faltan = [k for k in recomendados if k not in data]
    cuenta = ((data.get("correo") or {}).get("cuenta") or "").strip()
    avisos = []
    if not cuenta:
        avisos.append("correo.cuenta vacío: el skill debe autodetectar la cuenta")
    return {"ok": True, "claves_top": sorted(data.keys()),
            "campos_recomendados_ausentes": faltan, "avisos": avisos}


def _cargar_config(ruta):
    try:
        import yaml
    except ImportError:
        raise SystemExit("El modo determinista requiere PyYAML: "
                         "pip install pyyaml --break-system-packages")
    if not os.path.exists(ruta):
        aqui = os.path.dirname(os.path.abspath(__file__))
        # config.yaml vive un nivel por encima de scripts/, junto al SKILL.md.
        ruta = os.path.join(aqui, "..", "config.yaml")
    if not os.path.exists(ruta):
        raise SystemExit(
            "No se encontro config.yaml: ni el del usuario ni la plantilla "
            f"del plugin ({ruta}). Reinstala el plugin o usa --config <ruta>.")
    with open(ruta, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("ajustes")
    pa.add_argument("--correcciones",
                    default=os.path.expanduser("~/.email-triage/correcciones.jsonl"))
    ps = sub.add_parser("sanitizar")
    ps.add_argument("--archivo")
    ps.add_argument("--max-chars", type=int, default=1500)
    ps.add_argument("--asunto", default=None,
                    help="asunto del correo; también se escanea con S0")
    psc = sub.add_parser("scoring")
    psc.add_argument("--config",
                     default=os.path.expanduser("~/.email-triage/config.yaml"))
    psc.add_argument("--brief", action="store_true",
                     help="salida compacta: solo score/tier/ejes (ahorra tokens)")
    pv = sub.add_parser("validar-config")
    pv.add_argument("--config",
                    default=os.path.expanduser("~/.email-triage/config.yaml"))
    args = p.parse_args()
    if args.cmd == "ajustes":
        out = cmd_ajustes(args.correcciones)
    elif args.cmd == "scoring":
        payload = json.loads(sys.stdin.read() or "{}")
        out = cmd_scoring_dispatch(payload, _cargar_config(args.config),
                                   brief=args.brief)
    elif args.cmd == "validar-config":
        out = cmd_validar_config(args.config)
    else:
        if args.archivo:
            with open(args.archivo, encoding="utf-8", errors="replace") as fh:
                texto = fh.read()
        else:
            texto = sys.stdin.read()
        out = cmd_sanitizar(texto, args.max_chars, asunto=args.asunto)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
