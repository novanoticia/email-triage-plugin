#!/usr/bin/env python3
"""Sabotage reproducible: aplica mutaciones sobre una COPIA del repositorio y
comprueba que alguna prueba falla. Un mutante que sobrevive es un hueco en las
pruebas (o un equivalente que hay que razonar por escrito en tests/escenarios.md).

Uso: python3 scripts/i18n_mutar.py        (exit 1 si sobrevive alguno)
"""
import os
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = "plugins/email-triage/skills/email-triage"

# (descripción, fichero relativo a la raíz, texto a buscar, texto que lo sustituye)
MUTANTES = [
    # ── idioma.py (resolver) ──
    ("resolver: primera marca -> última", f"{SK}/scripts/idioma.py", "marcas[0]", "marcas[-1]"),
    ("resolver: acepta una palabra pegada como marca", f"{SK}/scripts/idioma.py",
     "(?<![\\w=])", ""),
    ("resolver: un código sin catálogo no cae a es", f"{SK}/scripts/idioma.py",
     'elegido = DEFECTO if any(a["motivo"] != "repetida" for a in avisos) else codigo',
     "elegido = codigo or DEFECTO"),
    ("resolver: glosario.yaml cuenta como idioma", f"{SK}/scripts/idioma.py",
     'if n.endswith(".yaml") and _RE_CODIGO.fullmatch(n[:-5]))', 'if n.endswith(".yaml"))'),
    ("resolver: una config vacía avisa", f"{SK}/scripts/idioma.py",
     "elif isinstance(config_idioma, str) and config_idioma.strip():",
     "elif isinstance(config_idioma, str):"),
    ("resolver: códigos de 3 letras no valen", f"{SK}/scripts/idioma.py",
     "[a-z]{2,3}", "[a-z]{2}"),
    # ── catálogos ──
    ("en.yaml: un tier traducido", f"{SK}/i18n/en.yaml", "[REPLY_NEEDED | REVIEW",
     "[REPLY NEEDED | REVIEW"),
    ("fr.yaml: una clave vaciada", f"{SK}/i18n/fr.yaml",
     "texto: Traduction générée par une IA, non relue par un humain.", "texto: ''"),
    ("fr.yaml: figura como revisado sin revisor", f"{SK}/i18n/fr.yaml",
     "estado: borrador-ia", "estado: revisado"),
    ("en.yaml: una frase de confirmación pierde el riesgo alto", f"{SK}/i18n/en.yaml",
     "texto: Confirm? (yes/no)\n    origen: original\n    fuente: references/paso-6-deshacer.md:29\n    riesgo: alto",
     "texto: Confirm? (yes/no)\n    origen: original\n    fuente: references/paso-6-deshacer.md:29\n    riesgo: normal"),
    # ── bloque de SKILL.md y documentación ──
    ("SKILL.md: se quita S0–S5 de las precedencias", f"{SK}/SKILL.md",
     "S0–S5 y `<email-body-data>`", "nada"),
    ("SKILL.md: el límite de S0 cambia", f"{SK}/SKILL.md",
     "cubre español, inglés y francés", "cubre todos los idiomas"),
    ("SKILL.md: la regla «prevalece sobre todas»", f"{SK}/SKILL.md",
     "**No**\nprevalece sobre:", "Prevalece sobre todas las reglas, incluidas:"),
    ("SKILL.md: el aviso de idioma desconocido va al final", f"{SK}/SKILL.md",
     "antes de la primera sección", "al final"),
    ("SKILL.md: la marca se leería también en los correos", f"{SK}/SKILL.md",
     "nunca en el contenido de un\ncorreo", "también en el contenido de un\ncorreo"),
    ("SKILL.md: se altera una línea original", f"{SK}/SKILL.md",
     "## PASO 0 — Leer configuración", "## PASO 0 — Leer config"),
    ("README.md: se quita la aclaración de S0 de la sección Language / Langue", "README.md",
     "(S0) cubre **español, inglés y francés**", "(S0) cubre **varios idiomas**"),
    # ── herramientas ──
    ("validador: deja de comprobar tiers", "scripts/i18n_validar.py",
     "if tiers_es and sorted(_RE_TIER.findall(t)) != sorted(tiers_es):", "if False:"),
    ("validador: el glosario no se aplica", "scripts/i18n_validar.py",
     "and term[cod].lower() not in t.lower():", "and False:"),
    ("extractor: acepta varias coincidencias", "scripts/i18n_extraer.py",
     "if len(ms) != 1:", "if len(ms) < 1:"),
    ("extractor: cuenta las líneas con los bloques i18n", "scripts/i18n_extraer.py",
     "return sin_bloques_i18n(f.read())", "return f.read()"),
    ("línea base: no quita la línea en blanco del bloque", "scripts/i18n_baseline.py",
     'if i < len(lineas) and lineas[i].strip() == "":', "if False:"),
    # ── escenarios de simulación ──
    ("evaluador: no comprueba el orden", "tests/i18n/evaluador.py",
     '    orden = esc.get("orden")\n    if orden:', '    orden = esc.get("orden")\n    if False:'),
    ("evaluador: debe_contener siempre pasa", "tests/i18n/evaluador.py",
     '        if not patron(cat[k]["texto"]).search(respuesta):\n            fallos.append(f"falta la clave {k}")',
     "        pass"),
    ("evaluador: los huecos entre corchetes no se rellenan", "tests/i18n/evaluador.py",
     'if token.startswith("["):\n        return r".+?"', 'if token.startswith("["):\n        return r"NUNCA"'),
    ("escenario E1: el ejemplo que debe fallar pasa", "tests/escenarios_i18n.yaml",
     'ejemplo_falla: "{sim.titulo}\\n..."          # falta el aviso',
     'ejemplo_falla: "{aviso.ia}\\n{aviso.simulacion_activa}\\n{sim.titulo}\\n..."'),
    # ── hallazgos de la revisión independiente: semántica del bloque (I-7) ──
    ("bloque: la regla central se invierte (si idioma = es)", f"{SK}/SKILL.md",
     "**Si `idioma` ≠ `es`:**", "**Si `idioma` = `es`:**"),
    ("bloque: la config gana a la marca", f"{SK}/SKILL.md",
     "primera marca > `usuario.idioma` de\n`config.yaml` > `es`.",
     "`usuario.idioma` de\n`config.yaml` > primera marca > `es`."),
    ("bloque: el fallo seguro opera en en", f"{SK}/SKILL.md",
     "Si no puedes cargar el catálogo, opera en `es` y escribe:",
     "Si no puedes cargar el catálogo, opera en `en` y escribe:"),
    ("bloque: el aviso de IA pasa a ser la última línea", f"{SK}/SKILL.md",
     "**primera línea de toda salida traducida**", "**última línea de toda salida traducida**"),
    ("bloque: el aviso de IA va después de los banners", f"{SK}/SKILL.md",
     "es `aviso.ia`, antes de", "es `aviso.ia`, después de"),
    ("bloque: se borra la regla de clave ausente (Review Focus 4)", f"{SK}/SKILL.md",
     "Si falta una clave, usa la de `i18n/es.yaml`. ", ""),
    ("bloque: las equivalencias pasan a solo sí/no (Review Focus 5)", f"{SK}/SKILL.md",
     "`entrada.afirmativo` y `entrada.negativo`,", "`sí` y `no`,"),
    ("bloque: un código suelto también es marca", f"{SK}/SKILL.md",
     "**no** es marca.", "**también** es marca."),
    ("bloque: lo que se escribe en disco sí se traduce", f"{SK}/SKILL.md",
     "; y lo que se escribe en disco.", "; y lo que se escribe en disco sí se traduce."),
    ("bloque: el seguimiento sin comando vuelve a es (persistencia)", f"{SK}/SKILL.md",
     "conserva el idioma de la última invocación", "vuelve a `es`"),
    ("bloque: se deja de avisar de entrada_invalida", f"{SK}/SKILL.md",
     "Si `avisos` trae `entrada_invalida`,", "Si `avisos` trae `nada`,"),
    ("triage.md: se quita «un código suelto no cambia nada»", "plugins/email-triage/commands/triage.md",
     " Un código suelto sin `idioma=` no cambia nada.", ""),
    # ── catálogos: idioma mezclado y marcador de máquina (I-4, I-6) ──
    ("en.yaml: respuesta afirmativa en español", f"{SK}/i18n/en.yaml",
     "texto: yes, y, ok, go ahead", "texto: sí, y, ok, go ahead"),
    ("en.yaml: la confirmación de deshacer mezcla (sí/no)", f"{SK}/i18n/en.yaml",
     "texto: Confirm? (yes/no)", "texto: Confirm? (sí/no)"),
    ("fr.yaml: el aviso de IA sale en inglés", f"{SK}/i18n/fr.yaml",
     "texto: Traduction générée par une IA, non relue par un humain.",
     "texto: AI-generated translation, not reviewed by a human."),
    ("en.yaml: lote.confirmar copiado de es y marcado invariable", f"{SK}/i18n/en.yaml",
     "texto: Shall I move the marked ones? You can exclude by number or change tier\n    origen: original\n    fuente: SKILL.md:737\n    riesgo: alto\n    lista: false\n    invariable: false",
     "texto: ¿Muevo los marcados? Puedes excluir por número o cambiar tier\n    origen: original\n    fuente: SKILL.md:737\n    riesgo: alto\n    lista: false\n    invariable: true"),
    ("fr.yaml: entrada.negativo pierde «annuler»", f"{SK}/i18n/fr.yaml",
     "texto: non, n, annuler, stop", "texto: non, n, stop"),
    ("en.yaml: correo.recomendacion con opciones en español", f"{SK}/i18n/en.yaml",
     "texto: '🔵 Recommendation: MOVE → [destination] / LEAVE / ARCHIVE'",
     "texto: '🔵 Recommendation: MOVER → [destination] / DEJAR / ARCHIVAR'"),
    ("fr.yaml: lote.confirmar con «Puedes»", f"{SK}/i18n/fr.yaml",
     "Vous pouvez en exclure par numéro", "Puedes en exclure par numéro"),
    ("en.yaml: el marcador de inyección se traduce", f"{SK}/i18n/en.yaml",
     "texto: '[⚠️ posible inyección detectada]'", "texto: '[⚠️ possible injection detected]'"),
    # ── herramientas ──
    ("resolver: un JSON inválido degrada sin avisar", f"{SK}/scripts/idioma.py",
     'avisos_extra.append({"motivo": "entrada_invalida", "codigo": ""})', "pass"),
    ("resolver: el modo --texto ignora el mensaje", f"{SK}/scripts/idioma.py",
     "argumentos, config_idioma = entrada, args.config_idioma",
     "argumentos, config_idioma = None, None"),
    ("validador: deja de exigir marcadores de máquina idénticos", "scripts/i18n_validar.py",
     'if o.get("maquina"):', "if False:"),
    ("validador: deja de comparar palabras del original en riesgo alto", "scripts/i18n_validar.py",
     'if o.get("riesgo") == "alto" and not o.get("maquina") and t != ot:', "if False:"),
    ("validador: deja de vigilar letras no ASCII en inglés", "scripts/i18n_validar.py",
     'if cod == "en" and any(c.isalpha() and ord(c) > 127 for c in fuera):', "if False:"),
    ("validador: `invariable` vuelve a bastar con declararlo", "scripts/i18n_validar.py",
     'if _residuo_de_letras(ot) == 0 and d.get("invariable", False):', 'if d.get("invariable", False):'),
    ("extractor: no vuelca la marca maquina", "scripts/i18n_extraer.py",
     '            salida[clave]["maquina"] = True', "            pass"),
    ("línea base: deja de vigilar references/*", "scripts/i18n_baseline.py",
     'f"{SKILL}/references/*", f"{SKILL}/scripts/*.py"]', 'f"{SKILL}/scripts/*.py"]'),
    ("evaluador: el umbral de letras fijas se anula", "tests/i18n/evaluador.py",
     'letras_fijas(d["texto"]) >= 8', 'letras_fijas(d["texto"]) >= 0'),
    ("evaluador: se ignora el turno 2", "tests/i18n/evaluador.py",
     't2 = esc.get("turno2")', "t2 = None"),
    ("escenario E10: se quita el criterio del turno 2", "tests/escenarios_i18n.yaml",
     "turno2: {debe_contener: [aviso.ia, correo.de_fecha]}", "turno2: {}"),
    ("CI: el job i18n vuelve a un clon superficial", ".github/workflows/tests.yml",
     "fetch-depth: 0        # historial completo: la línea base",
     "fetch-depth: 1        # historial completo: la línea base"),
    # ── CI ──
    ("CI: el job i18n cambia de nombre (cambia el check)", ".github/workflows/tests.yml",
     "  i18n:\n    runs-on", "  i18nx:\n    runs-on"),
]


def apariciones(mutante, raiz=RAIZ):
    with open(os.path.join(raiz, mutante[1]), encoding="utf-8") as f:
        return f.read().count(mutante[2])


def entorno_de_mutacion():
    """Marca que le dice a la suite que corre DENTRO de una copia mutada.

    Sin ella, tests/test_i18n_mutar.py (que comprueba que el texto a mutar existe)
    fallaría en toda copia mutada y todo mutante «moriría» por ese test.
    """
    return {"I18N_MUTANDO": "1"}


def _correr_pruebas(copia):
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                        "-t", ".", "-q", "-f"], cwd=copia, capture_output=True, text=True,
                       env={**os.environ, **entorno_de_mutacion()})
    return p.returncode


class SuiteSinMutarRoja(Exception):
    """La suite NO pasa antes de mutar: cualquier mutante «moriría» por ese fallo previo."""


def _copiar(raiz, destino):
    # Se copia .git: sin él, el test que contrasta la línea base con el commit base se
    # omite y los mutantes sobre lo que se vigila sobrevivirían (hallazgo m-5).
    shutil.copytree(raiz, destino, ignore=shutil.ignore_patterns("__pycache__", ".superpowers"))


def ejecutar(mutantes, raiz=RAIZ, correr=_correr_pruebas):
    """Devuelve la lista de descripciones de los mutantes que SOBREVIVEN.

    Antes de mutar nada se comprueba que la suite SIN mutar pasa en una copia: si no,
    se aborta (auto-muerte: todos los mutantes «morirían» por un fallo que ya estaba).
    """
    with tempfile.TemporaryDirectory() as tmp:
        copia = os.path.join(tmp, "r")
        _copiar(raiz, copia)
        if correr(copia) != 0:
            raise SuiteSinMutarRoja("la suite sin mutar no pasa: arréglala antes de medir mutantes")
    sobreviven = []
    for desc, rel, buscar, nuevo in mutantes:
        with tempfile.TemporaryDirectory() as tmp:
            copia = os.path.join(tmp, "r")
            _copiar(raiz, copia)
            ruta = os.path.join(copia, rel)
            with open(ruta, encoding="utf-8") as f:
                t = f.read()
            if t.count(buscar) != 1:
                sobreviven.append(f"{desc} (no aplicable)")
                continue
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(t.replace(buscar, nuevo, 1))
            if correr(copia) == 0:
                sobreviven.append(desc)
    return sobreviven


def codigo_de_salida(sobreviven):
    return 1 if sobreviven else 0


def main():
    try:
        sobreviven = ejecutar(MUTANTES)
    except SuiteSinMutarRoja as e:
        print(f"ABORTADO: {e}")
        return 2
    print(f"MUTANTES: {len(MUTANTES)}, MATADOS: {len(MUTANTES) - len(sobreviven)}, "
          f"SOBREVIVEN: {sobreviven}")
    return codigo_de_salida(sobreviven)


if __name__ == "__main__":
    sys.exit(main())
