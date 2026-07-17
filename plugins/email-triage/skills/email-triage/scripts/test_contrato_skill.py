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


def _invocaciones_doc():
    """[(fichero, linea, subcomando, [flags])] de todos los docs."""
    hallazgos = []
    for ruta in DOCS:
        if not os.path.exists(ruta):
            continue
        with open(ruta, encoding="utf-8") as fh:
            lineas = fh.readlines()
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
                hallazgos.append((os.path.basename(ruta), n, m.group(1),
                                  FLAG.findall(resto)))
            i += 1
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
        for nuclear in ("sanitizar", "scoring", "validar-config"):
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


if __name__ == "__main__":
    unittest.main()
