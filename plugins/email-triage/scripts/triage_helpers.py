#!/usr/bin/env python3
"""triage_helpers.py — Lógica determinista del plugin email-triage (v3.4).

Extrae a código las dos partes del SKILL.md que no deben depender de la
aritmética mental del modelo:

  ajustes    PASO 0.B — decay temporal y agregación de correcciones.jsonl
  sanitizar  Pipeline S0–S5 — limpieza del cuerpo ANTES de exponerlo al modelo

Uso:
  python3 triage_helpers.py ajustes [--correcciones RUTA]
  python3 triage_helpers.py sanitizar [--archivo RUTA] [--max-chars 1500]
                            (sin --archivo lee de stdin)

Salida: JSON por stdout. Solo stdlib (Python >= 3.9). Sin efectos laterales:
este script NUNCA escribe ficheros ni mueve correos.
"""
import argparse
import html as html_mod
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

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

def _decay(ts_iso, ahora):
    """×1.0 (<=30 días), ×0.5 (31-90), None (>90 o fecha ilegible)."""
    try:
        ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError, TypeError):
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


def cmd_ajustes(ruta):
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
        direccion = TIER_ORDEN[tc] - TIER_ORDEN[ta]
        if direccion == 0:
            continue
        ponderada = direccion * peso
        usadas.append({"ts": e.get("ts"), "direccion": direccion, "peso": peso})
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
    ultimas = sorted(usadas, key=lambda x: x["ts"] or "")[-20:]
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
    # Asignación de rol al modelo. Las frases genéricas ("you are", "eres",
    # "act as") solo disparan si en <=40 chars aparece un rol de IA; los
    # marcadores técnicos (system:, <system>, [INST]...) disparan por sí
    # solos. "you are receiving/subscrib..." queda excluido: es la fórmula
    # estándar de newsletters legítimas (falso positivo real en v3.4.0).
    # Trade-off documentado en tests: "you are the system administrator"
    # NO se marca ("system" se excluyó de los roles para no penalizar
    # correo legítimo de IT).
    ("rol_sistema",
     re.compile(r"(?:\byou are\b(?! receiving| subscrib)|\beres\b|"
                r"\bact as\b|\bact[uú]a como\b).{0,40}?\b" + _ROL_IA + r"\b"
                r"|^\s*system:|^\s*assistant:|<system>|\[INST\]|### ?Instruction",
                re.I | re.M | re.S)),
    # Solo delimitadores reales del protocolo. "^PASO \d" y "^score:" se
    # retiraron en v3.4.1: aparecen en correo legítimo (instrucciones de
    # trámites, resultados deportivos) y su valor defensivo era marginal.
    # "tier:" se mantiene anclado a los valores del protocolo.
    ("escape_delimitador",
     re.compile(r"</?email-body-data>|---EMAIL|^tier:\s*" + _TIER,
                re.I | re.M)),
    # Comandos al clasificador: anclados a objetos del dominio (carpeta,
    # inbox, tier, email) para no marcar usos humanos legítimos ("move
    # this to Thursday", "rate this support interaction").
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
    eliminados. Caza payloads ofuscados (&#105;gnore, ig<b>nore</b>)
    que el texto crudo esconde. No sustituye al crudo en la detección:
    los marcadores posicionales (^system:) y el escape de delimitador
    (</email-body-data>) solo son visibles en el crudo."""
    return re.sub(r"<[^>]+>", "", html_mod.unescape(texto))


def cmd_sanitizar(texto, max_chars=1500):
    original = len(texto)
    vistas = (texto, _vista_decodificada(texto))      # S0 en doble vista
    flags = sorted({nombre for nombre, pat in S0_PATRONES
                    for v in vistas if pat.search(v)})
    injection = bool(flags)

    # S3 primero como detección (no decodificar nunca)
    base64_block = re.search(r"(?:^[A-Za-z0-9+/=]{76,}\s*$\n?){2,}", texto, re.M)

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
        "patrones_detectados": flags,
        "ajuste_score": -3 if injection else 0,
        "longitud_original": original,
        "longitud_final": len(texto),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("ajustes")
    pa.add_argument("--correcciones",
                    default=os.path.expanduser("~/.email-triage/correcciones.jsonl"))
    ps = sub.add_parser("sanitizar")
    ps.add_argument("--archivo")
    ps.add_argument("--max-chars", type=int, default=1500)
    args = p.parse_args()
    if args.cmd == "ajustes":
        out = cmd_ajustes(args.correcciones)
    else:
        if args.archivo:
            with open(args.archivo, encoding="utf-8", errors="replace") as fh:
                texto = fh.read()
        else:
            texto = sys.stdin.read()
        out = cmd_sanitizar(texto, args.max_chars)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
