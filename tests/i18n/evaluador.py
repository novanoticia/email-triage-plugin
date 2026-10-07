"""Evaluador de escenarios i18n. Los textos esperados salen de los catálogos.

`catalogos` es {codigo: {clave: {"texto": ...}}}. En las plantillas de ejemplo,
`{clave}` usa el idioma esperado del escenario y `{xx:clave}` fuerza el idioma xx.

Los simuladores rellenan los huecos de las plantillas (`[Asunto]`, `HH:MM:SS`) y
los números (`X`, `N`, `X.X`): al comparar con una frase del catálogo, cada hueco
casa con cualquier relleno y cada letra-número con un número (o con la propia letra,
para poder usar la plantilla tal cual como ejemplo).
"""
import re

_HUECO = re.compile(r"(\[[^\]\n]*\]|\bHH:MM:SS\b|\bDD/MM\b|\bYYYY-MM-DD\b|\b[XYNMT]\b(?:\.[XN]\b)?)")


def _relleno(token):
    if token.startswith("["):
        return r".+?"
    if token == "HH:MM:SS":
        return r"(?:\d{2}:\d{2}:\d{2}|HH:MM:SS)"
    if token == "DD/MM":
        return r"(?:\d{1,2}/\d{1,2}|DD/MM)"
    if token == "YYYY-MM-DD":
        return r"(?:\d{4}-\d{2}-\d{2}|YYYY-MM-DD)"
    return r"(?:-?\d+(?:\.\d+)?|" + re.escape(token) + ")"


def patron(texto):
    """Regex que casa con la frase del catálogo con sus huecos y números rellenados."""
    if re.fullmatch(r"\[[^\[\]\n]*\]", texto):
        return re.compile(re.escape(texto))  # un marcador entero entre corchetes es literal
    partes = _HUECO.split(texto)
    return re.compile("".join(re.escape(p) if i % 2 == 0 else _relleno(p)
                              for i, p in enumerate(partes)))


def expandir(plantilla, catalogos, idioma):
    def sub(m):
        cod, clave = (m.group(1) or idioma + ":"), m.group(2)
        return catalogos[cod.rstrip(":")][clave]["texto"]
    return re.sub(r"\{(?:([a-z]{2,3}:))?([\w.]+)\}", sub, plantilla)


def evaluar(esc, respuesta, catalogos):
    fallos = []
    cat = catalogos[esc["idioma_esperado"]]
    for k in esc.get("debe_contener", []):
        if not patron(cat[k]["texto"]).search(respuesta):
            fallos.append(f"falta la clave {k}")
    for s in esc.get("debe_contener_texto", []):
        if s not in respuesta:
            fallos.append(f"falta el texto {s!r}")
    for k in esc.get("no_debe_contener", []):
        if patron(cat[k]["texto"]).search(respuesta):
            fallos.append(f"no debía aparecer la clave {k}")
    for otro in esc.get("no_debe_contener_de", []):
        for k, d in catalogos[otro].items():
            mio = cat.get(k, {}).get("texto")
            if d["texto"] != mio and len(d["texto"]) > 12 and patron(d["texto"]).search(respuesta):
                fallos.append(f"aparece una frase exclusiva de {otro}: {k}")
    orden = esc.get("orden")
    if orden:
        pos = []
        for k in orden:
            m = patron(cat[k]["texto"]).search(respuesta)
            pos.append(m.start() if m else -1)
        if -1 in pos or pos != sorted(pos):
            fallos.append(f"orden incorrecto de {orden}")
    return fallos
