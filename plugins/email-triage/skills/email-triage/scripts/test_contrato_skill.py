"""Gate de deriva doc<->codigo (NO1, auditoria 2026-07-17).

El codigo ya no confia en el modelo (escapado, scoring, locks son mecanismo),
pero el SKILL.md si confia en que sus invocaciones a triage_helpers.py
(subcomando + flags) sigan existiendo tal cual en el argparse real. Este test
extrae todas las invocaciones mencionadas en la doctrina (SKILL.md,
references/*.md, commands/triage.md, y el propio docstring del modulo) y las
valida contra la superficie real de _construir_parser(): coherencia
doc<->codigo como mecanismo, no como disciplina.

Gates F6/F8 (misma auditoria): ContratoHardRulesConfig fija que la tabla
4.A.1 del SKILL.md declare EXACTAMENTE las claves de config.hard_rules (ni
mas ni menos); ContratoCore12FuenteUnica fija que las copias legibles del
catalogo core (criterios-catalogo.md y config-veloz.yaml) sigan a la fuente
unica (config.yaml, criterios con `core: true`).

Gates ContratoDoctrina* (auditoria 2026-07-19): deriva doc<->doc. Nada
vigilaba que un documento citara bien las constantes que comparte con otro
fichero de verdad, y ahi vivia una clase entera de derivas (F2, F9, F10,
F23). Cada gate lee la verdad de su fuente natural (config.yaml de
plantilla, config-veloz.yaml, references/criterios-catalogo.md, la
plantilla mail-consolidado.applescript, el docstring de triage_helpers.py):
limites de volumen, protocolo de inyeccion, numeracion de criterios,
contador de SCRIPTs y completitud del bloque 'Uso:'.
"""
import os
import re
import unittest

import triage_helpers as th

AQUI = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.normpath(os.path.join(AQUI, ".."))
PLUGIN_DIR = os.path.normpath(os.path.join(SKILL_DIR, "..", ".."))

DOCS = [os.path.join(SKILL_DIR, "SKILL.md"),
        os.path.join(PLUGIN_DIR, "commands", "triage.md")]
refs = os.path.join(SKILL_DIR, "references")
if os.path.isdir(refs):
    DOCS += [os.path.join(refs, f) for f in sorted(os.listdir(refs))
             if f.endswith(".md")]

# "triage_helpers.py <subcomando> [--flags...]" — admite la comilla de
# cierre de una ruta entrecomillada ("<ruta>/triage_helpers.py" cmd).
INVOCACION = re.compile(r"triage_helpers\.py\"?\s+([a-z][a-z0-9-]*)")
FLAG = re.compile(r"(--[a-z][a-z0-9-]*)")

# Gate de interpolacion AppleScript (recomendacion no obvia, auditoria
# 2026-07-17, F1). Escanea los bloques ```applescript de la doctrina y prohibe
# un placeholder <...> crudo dentro de un string literal: esa es la clase de bug
# de F1 (SKILL:PASO 1.C interpolaba `<clave_hilo>`, derivado del asunto). La via
# segura es montar el script con montar-mover / montar-consulta-enviados, que
# escapan por mecanismo. Cierra la CLASE, no solo la instancia.
FENCE_APPLESCRIPT = re.compile(r"```applescript\n(.*?)```", re.DOTALL)
STRING_LIT = re.compile(r'"([^"\n]*)"')
PLACEHOLDER = re.compile(r"<[^<>\n]+>")
# Marcadores literales que SON el texto (no placeholders a sustituir):
MARCADORES_LITERALES_OK = {"<email-body-data>", "</email-body-data>"}
# El .applescript plantilla usa la convencion <<...>> (nombres de cuenta/carpeta
# del usuario), distinta y fuera de este gate: solo se vigilan los .md.


def _superficie():
    """{subcomando: {flags validos}} desde el argparse real."""
    import argparse
    parser = th._construir_parser()
    sub = next(a for a in parser._actions
               if isinstance(a, argparse._SubParsersAction))
    out = {}
    for nombre, sp in sub.choices.items():
        flags = set()
        for a in sp._actions:
            flags.update(o for o in a.option_strings if o.startswith("--"))
        out[nombre] = flags
    return out


DOCSTRING_LABEL = "triage_helpers.py:docstring"


def _extraer_invocaciones(fuente, lineas):
    """[(fuente, linea, subcomando, [flags])] de una lista de lineas."""
    hallazgos = []
    i = 0
    while i < len(lineas):
        linea, n = lineas[i], i + 1
        # Une continuaciones shell ("... \") para capturar los flags
        # que el SKILL parte en varias lineas.
        while linea.rstrip().endswith("\\") and i + 1 < len(lineas):
            i += 1
            linea = linea.rstrip()[:-1] + " " + lineas[i]
        m = INVOCACION.search(linea)
        if m:
            resto = linea[m.end():]
            hallazgos.append((fuente, n, m.group(1), FLAG.findall(resto)))
        i += 1
    return hallazgos


def _invocaciones_doc():
    """[(fuente, linea, subcomando, [flags])] de todos los docs Y del
    docstring de triage_helpers.py (la cabecera de este modulo lo promete:
    el bloque 'Uso:' tambien es doctrina y tambien deriva)."""
    hallazgos = []
    for ruta in DOCS:
        if not os.path.exists(ruta):
            continue
        with open(ruta, encoding="utf-8") as fh:
            hallazgos += _extraer_invocaciones(os.path.basename(ruta),
                                               fh.readlines())
    hallazgos += _extraer_invocaciones(DOCSTRING_LABEL,
                                       (th.__doc__ or "").splitlines(True))
    return hallazgos


class ContratoDocCodigo(unittest.TestCase):
    def test_hay_docs_que_vigilar(self):
        self.assertTrue(os.path.exists(DOCS[0]), "SKILL.md no encontrado")

    def test_subcomandos_del_doc_existen(self):
        superficie = _superficie()
        for fich, n, cmd, _ in _invocaciones_doc():
            self.assertIn(cmd, superficie,
                          "%s:%d invoca 'triage_helpers.py %s', que no existe "
                          "en el argparse real (deriva doc<->codigo)"
                          % (fich, n, cmd))

    def test_flags_del_doc_existen(self):
        superficie = _superficie()
        for fich, n, cmd, flags in _invocaciones_doc():
            validos = superficie.get(cmd, set())
            for f in flags:
                self.assertIn(f, validos,
                              "%s:%d usa '%s %s', flag inexistente; validos: %s"
                              % (fich, n, cmd, f, sorted(validos)))

    def test_superficie_minima_documentada(self):
        # Sanidad inversa: los subcomandos nucleares deben seguir mencionados
        # en la doctrina; si uno desaparece del SKILL.md, el modelo nunca lo
        # usara aunque exista.
        mencionados = {cmd for _, _, cmd, _ in _invocaciones_doc()}
        for nuclear in ("sanitizar", "scoring", "validar-config",
                        "calibrar"):
            self.assertIn(nuclear, mencionados,
                          "el subcomando '%s' ya no se menciona en la doctrina"
                          % nuclear)


class ContratoInterpolacionApplescript(unittest.TestCase):
    """Gate de la clase de F1 (auditoria 2026-07-17): ningun literal AppleScript
    de la doctrina puede interpolar un placeholder <...> crudo dentro de un
    string. La via segura es montar el script con montar-mover /
    montar-consulta-enviados, que escapan. Antes de QW1, PASO 1.C interpolaba
    `<clave_hilo>` (del asunto) y `<correo.cuenta>`."""

    def _ofensas(self):
        fuera = []
        for ruta in DOCS:
            if not os.path.exists(ruta):
                continue
            with open(ruta, encoding="utf-8") as fh:
                texto = fh.read()
            for bloque in FENCE_APPLESCRIPT.findall(texto):
                for lit in STRING_LIT.findall(bloque):
                    if lit in MARCADORES_LITERALES_OK:
                        continue
                    if PLACEHOLDER.search(lit):
                        fuera.append((os.path.basename(ruta), lit))
        return fuera

    def test_ningun_placeholder_crudo_en_literal_applescript(self):
        ofensas = self._ofensas()
        self.assertFalse(
            ofensas,
            "Literal(es) AppleScript con placeholder crudo — usa montar-mover / "
            "montar-consulta-enviados (escapan por mecanismo): %s" % ofensas)

    def test_el_gate_detecta_una_interpolacion_inyectada(self):
        # Sanidad: el gate NO es vacuo. Un bloque applescript con `"<x>"` debe
        # ser detectado por el detector (si no, el gate de arriba no protege).
        bloque = 'tell application "Mail"\n    set a to "<clave_hilo>"\nend tell\n'
        lits = STRING_LIT.findall(bloque)
        hostiles = [l for l in lits
                    if l not in MARCADORES_LITERALES_OK and PLACEHOLDER.search(l)]
        self.assertIn("<clave_hilo>", hostiles)


# ─── Gates F6/F8 (auditoria 2026-07-17): deriva doctrina<->config ──────────
# F6: la tabla 4.A.1 del SKILL.md declara las claves de `config.hard_rules`
# que el modelo puede pasar en el array `hard_rules` del scoring. Si doctrina
# y config divergen, _aplica_hard_rules manda la clave a 'ignorados' ("no
# definida en config") y el boost se pierde EN SILENCIO. F8: el catalogo core
# vive en tres sitios (config.yaml `core: true` —fuente unica—, el listado
# legible de references/criterios-catalogo.md y el comentario '# Core:' de
# config-veloz.yaml); nada detectaba que divergieran. Ambos gates convierten
# esa deriva en fallo de test. Si un extractor deja de encontrar su seccion
# (heading renombrado, formato cambiado), el test de no-vacuidad de cada gate
# falla en vez de dejar pasar una igualdad vacia.
RE_SECCION_HARD_RULES = re.compile(
    r"^####.*Hard rules deterministas.*$", re.IGNORECASE | re.MULTILINE)
RE_FILA_CLAVE = re.compile(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|", re.MULTILINE)
RE_SECCION_CORE_CATALOGO = re.compile(
    r"^####.*Criterios prioritarios.*$", re.IGNORECASE | re.MULTILINE)
RE_ITEM_CORE = re.compile(r"^\s*\d{1,2}\.\s+`([a-z][a-z0-9_]*)`", re.MULTILINE)
RE_CORE_VELOZ_INICIO = re.compile(r"#\s*Core:\s*(.*)")
RE_HEADING_MD = re.compile(r"^#{1,4}\s", re.MULTILINE)
RE_NOMBRE_CRITERIO = re.compile(r"[a-z][a-z0-9_]*\Z")


def _seccion_md(ruta, re_heading_seccion):
    """Texto entre el heading que casa con re_heading_seccion y el siguiente
    heading markdown (o EOF). '' si el fichero o el heading no existen."""
    if not os.path.exists(ruta):
        return ""
    with open(ruta, encoding="utf-8") as fh:
        texto = fh.read()
    m = re_heading_seccion.search(texto)
    if not m:
        return ""
    resto = texto[m.end():]
    fin = RE_HEADING_MD.search(resto)
    return resto[:fin.start()] if fin else resto


def _cargar_config_repo():
    import yaml
    with open(os.path.join(SKILL_DIR, "config.yaml"), encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _hard_rules_doctrina():
    """Claves de config.hard_rules que declara la tabla 4.A.1 del SKILL.md
    (primera celda de cada fila, entre backticks)."""
    return RE_FILA_CLAVE.findall(_seccion_md(DOCS[0], RE_SECCION_HARD_RULES))


def _hard_rules_config():
    """Claves reales de la seccion hard_rules: de config.yaml."""
    return [k for k in (_cargar_config_repo().get("hard_rules") or {})
            if isinstance(k, str)]


def _core_config():
    """Criterios con core: true en config.yaml (fuente unica del core-12)."""
    crits = _cargar_config_repo().get("criterios_epistemicos") or {}
    return [k for k, v in crits.items()
            if isinstance(v, dict) and v.get("core") is True]


def _core_catalogo():
    """Nombres canonicos del listado core de references/criterios-catalogo.md
    (items numerados '1. `nombre` (n)' bajo 'Criterios prioritarios')."""
    ruta = os.path.join(SKILL_DIR, "references", "criterios-catalogo.md")
    return RE_ITEM_CORE.findall(_seccion_md(ruta, RE_SECCION_CORE_CATALOGO))


def _core_config_veloz():
    """Nombres del comentario '# Core: ...' de config-veloz.yaml
    (comportamiento_veloz.solo_criterios_core). El bloque termina en la
    linea de comentario que acaba en '.' o al acabarse el comentario."""
    ruta = os.path.join(SKILL_DIR, "config-veloz.yaml")
    if not os.path.exists(ruta):
        return []
    trozos, dentro = [], False
    with open(ruta, encoding="utf-8") as fh:
        for linea in fh:
            if not dentro:
                m = RE_CORE_VELOZ_INICIO.search(linea)
                if not m:
                    continue
                dentro, trozo = True, m.group(1)
            else:
                s = linea.strip()
                if not s.startswith("#"):
                    break
                trozo = s.lstrip("#")
            trozos.append(trozo)
            if trozo.rstrip().endswith("."):
                break
    return [t for t in re.split(r"[,.\s]+", " ".join(trozos))
            if RE_NOMBRE_CRITERIO.match(t)]


class ContratoHardRulesConfig(unittest.TestCase):
    """Gate de F6 (auditoria 2026-07-17): la tabla 4.A.1 del SKILL.md y la
    seccion hard_rules: de config.yaml deben declarar EXACTAMENTE las mismas
    claves. Antes, la tabla 4.A presentaba ~17 fuentes de puntos como si todas
    fueran claves del config cuando solo 6 lo son: pasar 'remitente_prioritario'
    en el array hard_rules caia a ignorados y el boost se perdia en silencio;
    los boosts de calibracion/keywords van por extra_points (4.A.2)."""

    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML no instalado")

    def test_gate_no_vacuo(self):
        self.assertTrue(
            _hard_rules_doctrina(),
            "el extractor no saco ninguna clave de la tabla 4.A.1 del "
            "SKILL.md (¿heading 'Hard rules deterministas' renombrado o "
            "formato de fila '| `clave` |' cambiado?)")
        self.assertTrue(_hard_rules_config(),
                        "config.yaml sin claves en la seccion hard_rules:")

    def test_tabla_4a1_es_exactamente_config_hard_rules(self):
        doc, cfg = set(_hard_rules_doctrina()), set(_hard_rules_config())
        self.assertEqual(
            doc, cfg,
            "Deriva doctrina<->config en hard_rules. Solo en SKILL.md 4.A.1: "
            "%s; solo en config.yaml: %s. Una clave que no este en AMBOS "
            "sitios se pierde en silencio (_aplica_hard_rules -> ignorados, "
            "'no definida en config')."
            % (sorted(doc - cfg), sorted(cfg - doc)))


class ContratoCore12FuenteUnica(unittest.TestCase):
    """Gate de F8 (auditoria 2026-07-17): el catalogo core esta en TRES sitios
    — config.yaml (`core: true`, fuente unica), references/criterios-catalogo.md
    (listado legible, util en modo veloz sin cargar el config) y el comentario
    de config-veloz.yaml (solo_criterios_core). SKILL.md promete 'fuente unica'
    pero nada verificaba que las copias legibles siguieran al config. Este gate
    lo convierte en mecanismo: los tres conjuntos deben ser identicos."""

    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML no instalado")

    def test_gate_no_vacuo(self):
        self.assertTrue(_core_config(),
                        "config.yaml sin criterios con core: true")
        self.assertTrue(
            _core_catalogo(),
            "el extractor no saco nombres del listado core de "
            "criterios-catalogo.md (¿heading 'Criterios prioritarios' "
            "renombrado o formato '1. `nombre`' cambiado?)")
        self.assertTrue(
            _core_config_veloz(),
            "el extractor no saco nombres del comentario '# Core: ...' de "
            "config-veloz.yaml")

    def test_core_identico_en_las_tres_fuentes(self):
        cfg = set(_core_config())
        for etiqueta, copia in (
                ("references/criterios-catalogo.md", set(_core_catalogo())),
                ("config-veloz.yaml (# Core:)", set(_core_config_veloz()))):
            self.assertEqual(
                cfg, copia,
                "Deriva del core respecto a config.yaml (fuente unica) en "
                "%s. Solo en config.yaml: %s; solo en la copia: %s"
                % (etiqueta, sorted(cfg - copia), sorted(copia - cfg)))

    def test_core_son_doce(self):
        # La doctrina (SKILL.md 4.B y criterios-catalogo.md) promete en prosa
        # "12 criterios core". Si la cardinalidad cambia legitimamente, hay
        # que actualizar esa prosa Y este numero a la vez.
        self.assertEqual(
            len(set(_core_config())), 12,
            "config.yaml declara %d criterios core: true; la doctrina "
            "promete 12" % len(set(_core_config())))


class ContratoPlaceholdersApplescript(unittest.TestCase):
    """Gate de F26 (auditoria 2026-07-19): la plantilla references/
    mail-consolidado.applescript se rellena a mano (sus <<...>>), FUERA del gate
    de interpolacion de los .md (que solo mira bloques ```applescript). Este gate
    la vigila aparte: (1) inventaria sus placeholders y falla si aparece uno no
    documentado —obligando a declararlo y darle regla de escapado—; (2) exige que
    la plantilla conserve la REGLA DE ESCAPADO (pasar cuenta/carpetas por
    escapar-applescript antes de sustituir). Cierra la clase, no una instancia."""

    RUTA = os.path.join(SKILL_DIR, "references", "mail-consolidado.applescript")
    # Inventario canonico. Los 4 primeros son nombres de cuenta/carpeta (se
    # escapan con `escapados`); los 2 <<LISTA_*>> son las listas de message-ids
    # (se rellenan con `lista_applescript`). Un placeholder nuevo debe entrar
    # aqui Y recibir su regla de escapado en la cabecera de la plantilla.
    PLACEHOLDERS_DOCUMENTADOS = {
        "<<CUENTA>>", "<<ORIGEN>>", "<<DESTINO_REVIEW>>", "<<DESTINO_ARCHIVE>>",
        "<<LISTA_REVIEW>>", "<<LISTA_ARCHIVE>>",
    }
    RE_PLACEHOLDER = re.compile(r"<<[^<>\n]+>>")

    def _texto(self):
        if not os.path.exists(self.RUTA):
            return ""
        with open(self.RUTA, encoding="utf-8") as fh:
            return fh.read()

    def test_plantilla_existe(self):
        self.assertTrue(os.path.exists(self.RUTA),
                        "mail-consolidado.applescript no encontrado")

    def test_gate_no_vacuo(self):
        # Si el formato cambia y no se detecta ningun placeholder, el gate no
        # debe pasar en vacio (dejaria de proteger sin avisar).
        hallados = set(self.RE_PLACEHOLDER.findall(self._texto()))
        self.assertTrue(
            hallados,
            "no se detecto ningun placeholder <<...>> en la plantilla "
            "(¿convencion <<...>> cambiada?)")

    def test_placeholders_todos_documentados(self):
        hallados = set(self.RE_PLACEHOLDER.findall(self._texto()))
        no_doc = hallados - self.PLACEHOLDERS_DOCUMENTADOS
        self.assertFalse(
            no_doc,
            "Placeholder(s) <<...>> sin documentar en la plantilla: %s. "
            "Declaralos en PLACEHOLDERS_DOCUMENTADOS y dales regla de escapado "
            "en la cabecera del .applescript." % sorted(no_doc))

    def test_inventario_sin_placeholders_obsoletos(self):
        # Si un placeholder documentado desaparece, el inventario quedo obsoleto:
        # hay que actualizarlo para que el gate no proteja fantasmas.
        hallados = set(self.RE_PLACEHOLDER.findall(self._texto()))
        obsoletos = self.PLACEHOLDERS_DOCUMENTADOS - hallados
        self.assertFalse(
            obsoletos,
            "Placeholder(s) documentados que ya no aparecen en la plantilla: %s. "
            "Actualiza PLACEHOLDERS_DOCUMENTADOS." % sorted(obsoletos))

    def test_plantilla_conserva_regla_de_escapado(self):
        texto = self._texto()
        self.assertIn(
            "REGLA DE ESCAPADO", texto,
            "la plantilla perdio la ancla 'REGLA DE ESCAPADO' de su cabecera")
        self.assertIn(
            "escapar-applescript", texto,
            "la plantilla ya no instruye pasar cuenta/carpetas por "
            "escapar-applescript antes de sustituir los <<...>>")

# ─── Gates ContratoDoctrina* (auditoria 2026-07-19): deriva doc<->doc ──────
# El gate historico de este fichero vigila doc<->codigo; nada vigilaba
# doc<->doc, y ahi vivia toda una clase de derivas (F2, F9, F10, F23):
# referencias-fallback congeladas mientras el SKILL avanzaba, constantes
# numericas duplicadas que divergen, contadores desactualizados. Esta
# familia lee la VERDAD de su fuente natural (config.yaml de plantilla,
# config-veloz.yaml, references/criterios-catalogo.md, la plantilla
# mail-consolidado.applescript, el docstring de triage_helpers.py) y exige
# que cada documento que cite esas constantes las cite bien. Determinista:
# solo ficheros del repo relativos a este test; sin red y sin HOME. PyYAML:
# skipTest SOLO en las comprobaciones que parsean YAML.

RUTA_MANEJO_ERRORES = os.path.join(SKILL_DIR, "references",
                                   "manejo-errores.md")
RUTA_SANITIZACION = os.path.join(SKILL_DIR, "references",
                                 "sanitizacion-manual.md")
RUTA_CATALOGO = os.path.join(SKILL_DIR, "references",
                             "criterios-catalogo.md")
RUTA_PLANTILLA_AS = os.path.join(SKILL_DIR, "references",
                                 "mail-consolidado.applescript")
RUTA_CONFIG_VELOZ = os.path.join(SKILL_DIR, "config-veloz.yaml")

RE_VELOZ_EN_SKILL = re.compile(
    r"`max_caracteres_cuerpo: (\d+)`, `max_lineas_cuerpo: (\d+)`")
RE_VS_EQUILIBRADO = re.compile(
    r"max_caracteres_cuerpo:\s*\d+\s*#[^\n]*\(vs (\d+) equilibrado\)")
RE_VS_LINEAS = re.compile(r"max_lineas_cuerpo:\s*\d+\s*#[^\n]*\(vs (\d+)\)")
RE_CARACTERES_MANEJO = re.compile(
    r"puntuacion\.max_caracteres_cuerpo[^(]*\(config, (\d+) por defecto\)")
RE_LINEAS_MANEJO = re.compile(
    r"puntuacion\.max_lineas_cuerpo[^(]*"
    r"\(config, (\d+) por defecto; (\d+) en veloz\)")
RE_PERFILES_SANITIZACION = re.compile(r"(\d+) rápido / (\d+) equilibrado")
RE_PROTOCOLO_SKILL = re.compile(
    r"\*\*Protocolo si hay inyección detectada\*\*")
RE_PROTOCOLO_SANITIZACION = re.compile(
    r"\*\*Si se detecta un patrón de riesgo alto\*\*")
RE_PASO_NUMERADO = re.compile(r"^(\d+)\.\s", re.MULTILINE)
RE_FILA_CATALOGO = re.compile(r"\|\s*(\d{1,2})\s*\|\s*\*\*(.+?)\*\*\s*\|")
RE_GRUPO_CATALOGO = re.compile(r"\*\*GRUPO ([A-Z]) — ")
RE_CORE_NUMERADO = re.compile(
    r"^\s*\d{1,2}\.\s+`([a-z0-9_]+)`\s+\((\d+)\)", re.MULTILINE)
RE_REF_CRITERIOS_GRUPO = re.compile(
    r"criterios?\s+(\d+)\s*[-–]\s*(\d+)\s*(?:del\s+|\(\s*)"
    r"((?:Grupo\s+[A-Z])(?:\s*\+\s*Grupo\s+[A-Z])*)")
RE_BLOQUE_SCRIPT_AS = re.compile(r"^-- SCRIPT (\d+) — ", re.MULTILINE)
RE_RANGO_SCRIPTS = re.compile(r"SCRIPTs?\s+(\d+)\s*[-–]\s*(\d+)")
RE_SCRIPT_SUELTO = re.compile(r"SCRIPTs?\s+(\d+)(?:\s*y\s*(\d+))?")
STOPWORDS_NOMBRE_CRITERIO = {"de", "del", "la", "el", "los", "las", "vs",
                             "the"}
# El catalogo muestra nombres legibles y el config claves canonicas; casi
# todos casan quitando stopwords y acentos. Las excepciones legitimas van
# aqui (nombre visible en minusculas -> clave del config). Si renombras un
# criterio, actualiza catalogo/config y, si hace falta, este alias.
ALIAS_NOMBRE_CATALOGO = {"apertura de opciones": "abre_opciones"}
FRASE_MATIZ_CATALOGO = ("la numeración número↔criterio solo existe en el "
                        "catálogo")


def _texto_doc(ruta):
    """Contenido del fichero o '' si no existe (los tests de no-vacuidad
    convierten ese '' en fallo accionable, no en pase silencioso)."""
    if not os.path.exists(ruta):
        return ""
    with open(ruta, encoding="utf-8") as fh:
        return fh.read()


def _plano(texto):
    """Colapsa whitespace: casa frases partidas por el ajuste de linea."""
    return re.sub(r"\s+", " ", texto)


def _requiere_yaml(tc):
    try:
        import yaml  # noqa: F401
    except ImportError:
        tc.skipTest("PyYAML no instalado")


def _cargar_config_veloz():
    import yaml
    with open(RUTA_CONFIG_VELOZ, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _bloque_tras(texto, re_ancla):
    """Texto desde el ancla hasta la siguiente linea que abre en '**'."""
    m = re_ancla.search(texto)
    if not m:
        return ""
    resto = texto[m.end():]
    fin = re.search(r"^\*\*", resto, re.MULTILINE)
    return resto[:fin.start()] if fin else resto


def _catalogo_filas():
    """[(numero, nombre_visible, grupo)] de las tablas del catalogo, en el
    orden del fichero. El grupo es el del ultimo heading '**GRUPO X — '."""
    filas, grupo = [], None
    for linea in _texto_doc(RUTA_CATALOGO).splitlines():
        m = RE_GRUPO_CATALOGO.match(linea)
        if m:
            grupo = m.group(1)
            continue
        m = RE_FILA_CATALOGO.match(linea)
        if m and grupo:
            filas.append((int(m.group(1)), m.group(2).strip(), grupo))
    return filas


def _grupos_catalogo():
    """{letra: {numeros}} segun las tablas del catalogo."""
    grupos = {}
    for num, _, grupo in _catalogo_filas():
        grupos.setdefault(grupo, set()).add(num)
    return grupos


def _tokens_nombre(texto):
    """Tokens comparables de un nombre de criterio: minusculas, sin acentos
    y sin stopwords ('Cambio de predicciones' ~ 'cambio_predicciones')."""
    import unicodedata
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return tuple(t for t in re.findall(r"[a-z0-9]+", texto.lower())
                 if t not in STOPWORDS_NOMBRE_CRITERIO)


def _scripts_reales():
    """Numeros de bloque '-- SCRIPT N — ' reales de la plantilla."""
    return sorted(int(n) for n in
                  RE_BLOQUE_SCRIPT_AS.findall(_texto_doc(RUTA_PLANTILLA_AS)))


class ContratoDoctrinaVolumen(unittest.TestCase):
    """Gate de la clase de F9 (auditoria 2026-07-19): la doctrina de limites
    de volumen vive en references/manejo-errores.md (dos numeros de
    caracteres + uno de lineas) y sus VALORES por defecto en config.yaml
    (equilibrado) y config-veloz.yaml (veloz). Cada cita numerica en la
    doctrina debe seguir al YAML real, y sanitizacion-manual.md no puede
    re-hardcodear el limite (asi se congelo el fallback en su dia). QW2
    corrigio las instancias; esto impide que regresen."""

    def test_manejo_errores_menciona_las_claves_de_volumen(self):
        texto = _texto_doc(RUTA_MANEJO_ERRORES)
        for clave in ("max_caracteres_cuerpo", "max_lineas_cuerpo"):
            self.assertIn(
                clave, texto,
                "manejo-errores.md (doctrina de limites de volumen) ya no "
                "menciona `%s`: los limites se citan por clave de config, "
                "no por numero suelto" % clave)

    def test_skill_veloz_cita_los_valores_del_yaml_veloz(self):
        _requiere_yaml(self)
        veloz = _cargar_config_veloz().get("puntuacion") or {}
        m = RE_VELOZ_EN_SKILL.search(_texto_doc(DOCS[0]))
        self.assertTrue(
            m,
            "SKILL.md ya no cita los limites veloz como "
            "'`max_caracteres_cuerpo: N`, `max_lineas_cuerpo: N`' (item "
            "'Cuerpo recortado' del modo veloz); sin esa cita el gate no "
            "puede compararla con config-veloz.yaml")
        self.assertEqual(
            int(m.group(1)), veloz.get("max_caracteres_cuerpo"),
            "SKILL.md (modo veloz) dice max_caracteres_cuerpo: %s pero "
            "config-veloz.yaml dice %s"
            % (m.group(1), veloz.get("max_caracteres_cuerpo")))
        self.assertEqual(
            int(m.group(2)), veloz.get("max_lineas_cuerpo"),
            "SKILL.md (modo veloz) dice max_lineas_cuerpo: %s pero "
            "config-veloz.yaml dice %s"
            % (m.group(2), veloz.get("max_lineas_cuerpo")))

    def test_config_veloz_compara_con_el_equilibrado_real(self):
        _requiere_yaml(self)
        base = _cargar_config_repo().get("puntuacion") or {}
        crudo = _texto_doc(RUTA_CONFIG_VELOZ)
        m = RE_VS_EQUILIBRADO.search(crudo)
        self.assertTrue(
            m, "config-veloz.yaml perdio el comentario '(vs N equilibrado)' "
               "junto a max_caracteres_cuerpo; el gate no puede verificar "
               "que compara con el default real")
        self.assertEqual(
            int(m.group(1)), base.get("max_caracteres_cuerpo"),
            "config-veloz.yaml compara con '(vs %s equilibrado)' pero el "
            "default de config.yaml es %s"
            % (m.group(1), base.get("max_caracteres_cuerpo")))
        m = RE_VS_LINEAS.search(crudo)
        self.assertTrue(
            m, "config-veloz.yaml perdio el comentario '(vs N)' junto a "
               "max_lineas_cuerpo")
        self.assertEqual(
            int(m.group(1)), base.get("max_lineas_cuerpo"),
            "config-veloz.yaml compara con '(vs %s)' pero el default de "
            "config.yaml es %s" % (m.group(1), base.get("max_lineas_cuerpo")))

    def test_manejo_errores_cita_los_defaults_reales(self):
        _requiere_yaml(self)
        base = _cargar_config_repo().get("puntuacion") or {}
        veloz = _cargar_config_veloz().get("puntuacion") or {}
        plano = _plano(_texto_doc(RUTA_MANEJO_ERRORES))
        m = RE_CARACTERES_MANEJO.search(plano)
        self.assertTrue(
            m, "manejo-errores.md ya no cita "
               "'`puntuacion.max_caracteres_cuerpo` (config, N por defecto)'")
        self.assertEqual(
            int(m.group(1)), base.get("max_caracteres_cuerpo"),
            "manejo-errores.md dice que max_caracteres_cuerpo vale %s por "
            "defecto; config.yaml dice %s"
            % (m.group(1), base.get("max_caracteres_cuerpo")))
        m = RE_LINEAS_MANEJO.search(plano)
        self.assertTrue(
            m, "manejo-errores.md ya no cita '`puntuacion.max_lineas_cuerpo` "
               "(config, N por defecto; M en veloz)'")
        self.assertEqual(
            int(m.group(1)), base.get("max_lineas_cuerpo"),
            "manejo-errores.md dice que max_lineas_cuerpo vale %s por "
            "defecto; config.yaml dice %s"
            % (m.group(1), base.get("max_lineas_cuerpo")))
        self.assertEqual(
            int(m.group(2)), veloz.get("max_lineas_cuerpo"),
            "manejo-errores.md dice '%s en veloz' para max_lineas_cuerpo; "
            "config-veloz.yaml dice %s"
            % (m.group(2), veloz.get("max_lineas_cuerpo")))

    def test_sanitizacion_sin_limite_rehardcodeado(self):
        plano = _plano(_texto_doc(RUTA_SANITIZACION))
        self.assertIn(
            "max_caracteres_cuerpo", plano,
            "sanitizacion-manual.md (S5) debe citar la clave "
            "`puntuacion.max_caracteres_cuerpo` como origen del presupuesto")
        m = re.search(r"truncar a \d+", plano)
        self.assertIsNone(
            m,
            "sanitizacion-manual.md re-hardcodea el limite (%r): la clase "
            "de F9. Debe decir 'truncar a ese valor' citando "
            "`puntuacion.max_caracteres_cuerpo`, no congelar un numero que "
            "el config puede cambiar" % (m.group(0) if m else ""))

    def test_sanitizacion_cita_los_perfiles_reales(self):
        _requiere_yaml(self)
        base = _cargar_config_repo().get("puntuacion") or {}
        veloz = _cargar_config_veloz().get("puntuacion") or {}
        m = RE_PERFILES_SANITIZACION.search(
            _plano(_texto_doc(RUTA_SANITIZACION)))
        self.assertTrue(
            m, "sanitizacion-manual.md ya no cita 'N rápido / M equilibrado' "
               "en S5; el gate no puede verificar los perfiles")
        self.assertEqual(
            int(m.group(1)), veloz.get("max_caracteres_cuerpo"),
            "sanitizacion-manual.md dice '%s rápido' pero config-veloz.yaml "
            "dice %s" % (m.group(1), veloz.get("max_caracteres_cuerpo")))
        self.assertEqual(
            int(m.group(2)), base.get("max_caracteres_cuerpo"),
            "sanitizacion-manual.md dice '%s equilibrado' pero config.yaml "
            "dice %s" % (m.group(2), base.get("max_caracteres_cuerpo")))


class ContratoDoctrinaInyeccion(unittest.TestCase):
    """Gate de la clase de F2 (auditoria 2026-07-19): el protocolo de
    inyeccion vive DUPLICADO en SKILL.md (via script) y en
    references/sanitizacion-manual.md (fallback manual). QW1 los
    sincronizo; este gate fija los invariantes que divergieron entonces:
    cap de tier en AMBOS, misma cardinalidad de pasos y clausula de
    precedencia en el fallback."""

    def _bloques(self):
        return (
            ("SKILL.md",
             _bloque_tras(_texto_doc(DOCS[0]), RE_PROTOCOLO_SKILL)),
            ("references/sanitizacion-manual.md",
             _bloque_tras(_texto_doc(RUTA_SANITIZACION),
                          RE_PROTOCOLO_SANITIZACION)),
        )

    def test_gate_no_vacuo(self):
        for nombre, bloque in self._bloques():
            self.assertTrue(
                bloque.strip(),
                "no se encontro el bloque del protocolo de inyeccion en %s "
                "(¿ancla '**Protocolo si hay inyección detectada**' / "
                "'**Si se detecta un patrón de riesgo alto**' renombrada?)"
                % nombre)

    def test_cap_de_tier_en_ambos_documentos(self):
        for nombre, bloque in self._bloques():
            self.assertIn(
                "Capar el tier", bloque,
                "%s perdio el paso 'Capar el tier' del protocolo de "
                "inyeccion (la deriva original de F2)" % nombre)
            self.assertIn(
                "`REVIEW`", bloque,
                "%s ya no fija `REVIEW` como tier maximo tras una inyeccion"
                % nombre)

    def test_misma_cardinalidad_de_pasos(self):
        conteos = {}
        for nombre, bloque in self._bloques():
            pasos = [int(n) for n in RE_PASO_NUMERADO.findall(bloque)]
            self.assertEqual(
                pasos, list(range(1, len(pasos) + 1)),
                "los pasos numerados del protocolo en %s no son "
                "consecutivos desde 1: %s" % (nombre, pasos))
            conteos[nombre] = len(pasos)
        valores = sorted(set(conteos.values()))
        self.assertEqual(
            len(valores), 1,
            "el protocolo de inyeccion tiene distinta cardinalidad de "
            "pasos: %s — SKILL.md y sanitizacion-manual.md deben ir a la "
            "par (F2)" % conteos)
        self.assertEqual(
            valores[0], 6,
            "el protocolo de inyeccion tiene %d pasos y la doctrina fija "
            "6; si el protocolo cambia de verdad, actualiza SKILL.md, "
            "sanitizacion-manual.md y este numero A LA VEZ" % valores[0])

    def test_fallback_conserva_clausula_de_precedencia(self):
        self.assertIn(
            "manda el SKILL.md", _texto_doc(RUTA_SANITIZACION),
            "sanitizacion-manual.md perdio la clausula de precedencia "
            "('si difieren, manda el SKILL.md') que arbitra la copia "
            "duplicada del protocolo")


class ContratoDoctrinaNumeracionCriterios(unittest.TestCase):
    """Gate de F10 (auditoria 2026-07-19): references/criterios-catalogo.md
    es el UNICO portador del mapeo numero<->criterio (el config no numera:
    ordena). Se fija que (a) el catalogo numere 30 criterios consecutivos
    cuyos nombres sigan el ORDEN de criterios_epistemicos en config.yaml,
    (b) el listado core numere igual que el config, (c) toda referencia
    'criterios N-M (Grupo X)' de la doctrina case con las tablas, y (d)
    nadie declare el catalogo 'redundante' sin el matiz de que la
    numeracion solo vive alli."""

    def test_gate_no_vacuo(self):
        filas = _catalogo_filas()
        self.assertTrue(
            filas,
            "el extractor no saco ninguna fila numerada de "
            "criterios-catalogo.md (¿formato '| N | **Nombre** |' o "
            "headings '**GRUPO X — ' cambiados?)")
        numeros = [n for n, _, _ in filas]
        self.assertEqual(
            numeros, list(range(1, len(filas) + 1)),
            "la numeracion del catalogo no es consecutiva desde 1: %s"
            % numeros)
        self.assertEqual(
            sorted(_grupos_catalogo()), ["A", "B", "C", "D"],
            "el catalogo ya no tiene exactamente los grupos A-D: %s"
            % sorted(_grupos_catalogo()))

    def test_catalogo_numera_treinta_criterios(self):
        self.assertEqual(
            len(_catalogo_filas()), 30,
            "el catalogo numera %d criterios y la doctrina promete 30; si "
            "la cardinalidad cambia de verdad, actualiza catalogo, "
            "config.yaml y este numero a la vez" % len(_catalogo_filas()))

    def test_numeracion_sigue_al_orden_del_config(self):
        _requiere_yaml(self)
        claves = [k for k in (_cargar_config_repo()
                              .get("criterios_epistemicos") or {})]
        self.assertEqual(
            len(claves), 30,
            "config.yaml declara %d criterios_epistemicos, no 30"
            % len(claves))
        for numero, nombre, _ in _catalogo_filas():
            esperada = claves[numero - 1]
            alias = ALIAS_NOMBRE_CATALOGO.get(nombre.lower())
            coincide = (alias == esperada or
                        _tokens_nombre(nombre) ==
                        _tokens_nombre(esperada.replace("_", " ")))
            self.assertTrue(
                coincide,
                "fila %d del catalogo se llama '%s', pero la posicion %d "
                "de criterios_epistemicos en config.yaml es '%s'. El "
                "catalogo es el unico portador del mapeo numero<->criterio "
                "y debe seguir el orden del config (si renombraste o "
                "reordenaste, actualiza el otro lado o "
                "ALIAS_NOMBRE_CATALOGO)"
                % (numero, nombre, numero, esperada))

    def test_listado_core_numera_como_el_config(self):
        _requiere_yaml(self)
        claves = [k for k in (_cargar_config_repo()
                              .get("criterios_epistemicos") or {})]
        pares = RE_CORE_NUMERADO.findall(_texto_doc(RUTA_CATALOGO))
        self.assertTrue(
            pares,
            "el extractor no saco pares '`clave` (N)' del listado core de "
            "criterios-catalogo.md")
        for clave, numero in pares:
            self.assertIn(
                clave, claves,
                "el listado core del catalogo cita '%s', que no existe en "
                "criterios_epistemicos de config.yaml" % clave)
            self.assertEqual(
                claves.index(clave) + 1, int(numero),
                "el listado core del catalogo dice '`%s` (%s)' pero esa "
                "clave ocupa la posicion %d en config.yaml"
                % (clave, numero, claves.index(clave) + 1))

    def test_referencias_criterios_grupo_coherentes(self):
        grupos = _grupos_catalogo()
        encontradas = 0
        for ruta in DOCS:
            nombre = os.path.basename(ruta)
            for m in RE_REF_CRITERIOS_GRUPO.finditer(
                    _plano(_texto_doc(ruta))):
                encontradas += 1
                desde, hasta = int(m.group(1)), int(m.group(2))
                letras = re.findall(r"Grupo\s+([A-Z])", m.group(3))
                union = set()
                for letra in letras:
                    self.assertIn(
                        letra, grupos,
                        "%s referencia el Grupo %s, que no existe en el "
                        "catalogo" % (nombre, letra))
                    union |= grupos[letra]
                rango = set(range(desde, hasta + 1))
                self.assertTrue(
                    rango <= union,
                    "%s dice 'criterios %d-%d' de %s, pero segun el "
                    "catalogo ese/esos grupo(s) cubren %s — referencia "
                    "numerica incoherente con criterios-catalogo.md (asi "
                    "nacio F10: 'criterios 1-5 del Grupo B' cuando B es "
                    "2-5)" % (nombre, desde, hasta,
                              " + ".join("Grupo %s" % l for l in letras),
                              sorted(union)))
        self.assertGreaterEqual(
            encontradas, 1,
            "el escaner de referencias 'criterios N-M (Grupo X)' no "
            "encontro ninguna en la doctrina; si la frase cambio de forma, "
            "adapta RE_REF_CRITERIOS_GRUPO para que el gate siga vigilando")

    def test_redundancia_del_catalogo_siempre_con_matiz(self):
        for ruta in DOCS:
            nombre = os.path.basename(ruta)
            for parrafo in _texto_doc(ruta).split("\n\n"):
                plano = _plano(parrafo)
                if "redundante" not in plano:
                    continue
                if ("criterios-catalogo" not in plano
                        and "catálogo" not in plano):
                    continue
                self.assertIn(
                    FRASE_MATIZ_CATALOGO, plano,
                    "%s declara el catalogo 'redundante' sin el matiz "
                    "obligatorio (%r): las preguntas/pesos si estan en el "
                    "config, la NUMERACION no — solo vive en el catalogo "
                    "(F10)" % (nombre, FRASE_MATIZ_CATALOGO))
        self.assertIn(
            FRASE_MATIZ_CATALOGO, _plano(_texto_doc(DOCS[0])),
            "SKILL.md perdio la frase-matiz %r que aclara que la "
            "numeracion numero<->criterio solo existe en el catalogo"
            % FRASE_MATIZ_CATALOGO)


class ContratoDoctrinaContadorScripts(unittest.TestCase):
    """Gate de F23 (auditoria 2026-07-19): la verdad del numero de bloques
    'SCRIPT N' es la propia plantilla references/mail-consolidado.applescript
    (hoy 4; el 4o borra de disco los cuerpos crudos — privacidad). SKILL.md
    llego a vender 'SCRIPTs 1-3': quien siguiera esa prosa se saltaba la
    limpieza. Toda mencion agregada 'SCRIPTs 1-N' debe cubrir TODOS los
    bloques y toda mencion suelta 'SCRIPT N' debe existir en la plantilla."""

    def test_gate_no_vacuo(self):
        reales = _scripts_reales()
        self.assertTrue(
            reales,
            "no se detecto ningun bloque '-- SCRIPT N — ' en "
            "mail-consolidado.applescript (¿cabeceras renombradas?)")
        self.assertEqual(
            reales, list(range(1, len(reales) + 1)),
            "los bloques SCRIPT de la plantilla no son consecutivos desde "
            "1: %s" % reales)

    def test_menciones_coherentes_con_la_plantilla(self):
        reales = set(_scripts_reales())
        if not reales:
            self.fail("plantilla sin bloques SCRIPT (ver test_gate_no_vacuo)")
        tope = max(reales)
        menciones = 0
        for ruta in DOCS:
            nombre = os.path.basename(ruta)
            plano = _plano(_texto_doc(ruta))
            for m in RE_RANGO_SCRIPTS.finditer(plano):
                menciones += 1
                desde, hasta = int(m.group(1)), int(m.group(2))
                self.assertTrue(
                    set(range(desde, hasta + 1)) <= reales,
                    "%s menciona '%s' pero la plantilla solo tiene los "
                    "bloques %s" % (nombre, m.group(0), sorted(reales)))
                if desde == 1:
                    self.assertEqual(
                        hasta, tope,
                        "%s dice '%s' como si fueran todos, pero "
                        "mail-consolidado.applescript tiene %d bloques — "
                        "el %d (LIMPIEZA de cuerpos crudos, privacidad) "
                        "tambien es parte del protocolo (F23)"
                        % (nombre, m.group(0), tope, tope))
            sin_rangos = RE_RANGO_SCRIPTS.sub(" ", plano)
            for m in RE_SCRIPT_SUELTO.finditer(sin_rangos):
                for num in m.groups():
                    if num is None:
                        continue
                    menciones += 1
                    self.assertIn(
                        int(num), reales,
                        "%s menciona 'SCRIPT %s', que no existe en la "
                        "plantilla (bloques reales: %s)"
                        % (nombre, num, sorted(reales)))
        self.assertGreaterEqual(
            menciones, 1,
            "el escaner no encontro ninguna mencion 'SCRIPT N' en la "
            "doctrina; si la nomenclatura cambio, adapta RE_RANGO_SCRIPTS/"
            "RE_SCRIPT_SUELTO para que el gate siga vigilando")


class ContratoDoctrinaDocstringHelpers(unittest.TestCase):
    """La cabecera de este modulo promete validar 'el propio docstring del
    modulo' de triage_helpers.py: el docstring es doctrina (es la ayuda que
    lee quien abre el script) y tambien deriva. Se fija que (a) el
    docstring aporta invocaciones al inventario comun — con lo que los
    gates de subcomandos/flags de ContratoDocCodigo tambien lo validan — y
    (b) el bloque 'Uso:' lista TODOS los subcomandos reales (la omision
    detectada: montar-consulta-enviados no aparecia)."""

    def test_docstring_en_el_inventario(self):
        fuentes = {fuente for fuente, _, _, _ in _invocaciones_doc()}
        self.assertIn(
            DOCSTRING_LABEL, fuentes,
            "el docstring de triage_helpers.py ya no aporta ninguna "
            "invocacion al inventario del gate (la cabecera de este modulo "
            "promete vigilarlo)")

    def test_uso_lista_todos_los_subcomandos(self):
        en_docstring = {cmd for fuente, _, cmd, _ in _invocaciones_doc()
                        if fuente == DOCSTRING_LABEL}
        faltan = sorted(set(_superficie()) - en_docstring)
        self.assertFalse(
            faltan,
            "subcomando(s) reales que el bloque 'Uso:' del docstring de "
            "triage_helpers.py no lista: %s — un subcomando ausente de la "
            "ayuda de cabecera es invisible para quien la lea" % faltan)



if __name__ == "__main__":
    unittest.main()
