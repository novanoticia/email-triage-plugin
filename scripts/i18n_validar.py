#!/usr/bin/env python3
"""Validador de catálogos i18n (dev + CI). Requiere PyYAML.

Uso: python3 scripts/i18n_validar.py [DIR_I18N]    (exit 1 si hay errores)
"""
import os
import re
import sys

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_DEFECTO = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage", "i18n")
ESTADOS = {"referencia", "borrador-ia", "experimental", "revisado"}
_RE_COD = re.compile(r"[a-z]{2,3}")
_RE_TICKS = re.compile(r"`([^`]+)`")
_RE_HUECO = re.compile(r"\[[^\]\n]+\]")
_RE_TIER = re.compile(r"REPLY_NEEDED|REVIEW|READING_LATER|ARCHIVE")
_RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿⏰-⏿]️?")
_PROHIBIDO = re.compile(r"\b(TODO|TBD|XXX|FIXME)\b")
_REVISORES_INVALIDOS = {"ia", "ai", "claude", "ninguno", "nadie", ""}
# Palabras que pueden ser iguales en todos los idiomas sin que sea una frase sin traducir.
_NEUTRAS = {"tier", "score", "scoring", "total", "extra", "config", "yaml", "mail", "app",
            "gmail", "mcp", "macos", "prompt", "keywords", "text", "plain", "html", "undo",
            "real"}  # «real»: cognado es/en que es la misma palabra legítimamente
_RE_IDENT = re.compile(r"\S*_\S*")                      # identificadores: umbral_mover, destino_archive
_RE_PLACEHOLDER = re.compile(r"\b(?:HH:MM:SS|DD/MM|YYYY-MM-DD|[XYNMT]|X\.X)\b")


def _sin_codigo(texto):
    """Texto sin lo que va entre comillas invertidas (rutas, claves, tiers contractuales)."""
    return re.sub(r"`[^`]*`", " ", texto)


def _palabras(texto):
    """Palabras de 4+ letras, en minúscula, sin código ni identificadores."""
    limpio = _RE_TIER.sub(" ", _RE_IDENT.sub(" ", _sin_codigo(texto)))
    return set(re.findall(r"[^\W\d_]{4,}", limpio.lower()))


def _residuo_de_letras(texto):
    """Letras que quedan tras quitar lo que es igual en cualquier idioma (tiers, ids, X/N/HH:MM)."""
    limpio = _RE_IDENT.sub(" ", _sin_codigo(texto))
    limpio = _RE_TIER.sub(" ", limpio)
    limpio = _RE_PLACEHOLDER.sub(" ", limpio)
    limpio = re.sub(r"[^\W\d_]+", lambda m: " " if m.group(0).lower() in _NEUTRAS else m.group(0),
                    limpio)
    return sum(c.isalpha() for c in limpio)


def _cargar(ruta, errores):
    try:
        with open(ruta, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as e:
        errores.append(f"{os.path.basename(ruta)}: no se pudo leer ({e})")
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("frases"), dict):
        errores.append(f"{os.path.basename(ruta)}: estructura inválida (falta `frases`)")
        return None
    return doc


def _val(doc, cod, errores):
    estado, rev = doc.get("estado"), doc.get("revisado_por")
    if estado not in ESTADOS:
        errores.append(f"{cod}: estado {estado!r} desconocido")
    if estado == "revisado":
        if not rev or str(rev).strip().lower() in _REVISORES_INVALIDOS:
            errores.append(f"{cod}: estado revisado sin revisor humano válido ({rev!r})")


def validar(dir_i18n):
    errores = []
    cats = {}
    try:
        nombres = sorted(n[:-5] for n in os.listdir(dir_i18n)
                         if n.endswith(".yaml") and _RE_COD.fullmatch(n[:-5]))
    except OSError as e:
        return [f"no se pudo listar {dir_i18n}: {e}"]
    if "es" not in nombres:
        return ["falta es.yaml (referencia)"]
    for cod in nombres:
        doc = _cargar(os.path.join(dir_i18n, cod + ".yaml"), errores)
        if doc is not None:
            cats[cod] = doc
    if "es" not in cats:
        return errores
    es = cats["es"]["frases"]
    glos = []
    rg = os.path.join(dir_i18n, "glosario.yaml")
    if os.path.exists(rg):
        try:
            with open(rg, encoding="utf-8") as f:
                glos = (yaml.safe_load(f) or {}).get("terminos", [])
        except (OSError, yaml.YAMLError) as e:
            errores.append(f"glosario.yaml: no se pudo leer ({e})")
    for cod, doc in cats.items():
        _val(doc, cod, errores)
        fr = doc["frases"]
        if cod == "es":
            for k, d in fr.items():
                if not isinstance(d, dict) or not str(d.get("texto", "")).strip():
                    errores.append(f"es.{k}: texto vacío")
            continue
        for k in es:
            if k not in fr:
                errores.append(f"{cod}: falta la clave {k}")
        for k, d in fr.items():
            if k not in es:
                errores.append(f"{cod}: la clave {k} no existe en es")
                continue
            t = str(d.get("texto", "")) if isinstance(d, dict) else ""
            o = es[k]
            ot = str(o["texto"])
            if not t.strip():
                errores.append(f"{cod}.{k}: texto vacío")
                continue
            if _PROHIBIDO.search(t):
                errores.append(f"{cod}.{k}: contiene TODO/TBD/XXX")
            if _RE_TICKS.findall(t) != _RE_TICKS.findall(ot):
                errores.append(f"{cod}.{k}: texto contractual (entre comillas invertidas) distinto")
            # Solo en frases cuyo original nombra tiers: el verbo inglés «ARCHIVE»
            # coincide con el tier y no debe dar falso positivo en «MOVE / LEAVE / ARCHIVE».
            tiers_es = _RE_TIER.findall(ot)
            if tiers_es and sorted(_RE_TIER.findall(t)) != sorted(tiers_es):
                errores.append(f"{cod}.{k}: nombres de tiers distintos")
            if _RE_EMOJI.findall(t) != _RE_EMOJI.findall(ot):
                errores.append(f"{cod}.{k}: emojis distintos")
            if len(_RE_HUECO.findall(t)) != len(_RE_HUECO.findall(ot)):
                errores.append(f"{cod}.{k}: huecos entre corchetes distintos")
            if o.get("lista") and t.count("/") != ot.count("/"):
                errores.append(f"{cod}.{k}: número de opciones distinto")
            if o.get("maquina"):
                # Un marcador de máquina (lo emite un script o SKILL.md lo fija entre
                # comillas) no se traduce: es un contrato, no una frase.
                if t != ot:
                    errores.append(f"{cod}.{k}: marcador de máquina distinto del original "
                                   f"(debe ser idéntico)")
            elif t == ot:
                if _residuo_de_letras(ot) == 0 and d.get("invariable", False):
                    pass  # neutro de verdad (p. ej. «Total: N») y declarado
                elif d.get("invariable", False):
                    errores.append(f"{cod}.{k}: invariable no justificado (el texto tiene "
                                   f"palabras traducibles)")
                else:
                    errores.append(f"{cod}.{k}: idéntico al original y no marcado invariable")
            if o.get("riesgo") == "alto" and d.get("riesgo") != "alto":
                errores.append(f"{cod}.{k}: pierde la marca de riesgo alto")
            if o.get("riesgo") == "alto" and not o.get("maquina") and t != ot:
                comunes = (_palabras(t) & _palabras(ot)) - _NEUTRAS
                if comunes:
                    errores.append(f"{cod}.{k}: palabras del original sin traducir en una frase "
                                   f"de riesgo alto: {sorted(comunes)}")
            fuera = "" if o.get("maquina") else _sin_codigo(t)
            if cod != "es" and re.search("[¿¡]", fuera):
                errores.append(f"{cod}.{k}: caracteres de otro idioma (¿ ¡)")
            if cod == "en" and any(c.isalpha() and ord(c) > 127 for c in fuera):
                errores.append(f"{cod}.{k}: caracteres de otro idioma (letras no ASCII)")
            if cod == "fr" and re.search("[áíóúñÁÍÓÚÑ]", fuera):
                errores.append(f"{cod}.{k}: caracteres de otro idioma (ortografía española)")
            for term in glos:
                if cod in term and term["es"].lower() in ot.lower() \
                        and term[cod].lower() not in t.lower():
                    errores.append(f"{cod}.{k}: glosario: «{term['es']}» -> «{term[cod]}»")
    return errores


if __name__ == "__main__":
    errs = validar(sys.argv[1] if len(sys.argv) > 1 else DIR_DEFECTO)
    for e in errs:
        print("ERROR:", e)
    if errs:
        print(f"{len(errs)} error(es)")
        sys.exit(1)
    print("OK: catálogos válidos")
