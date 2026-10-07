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
     "cubre solo español e inglés", "cubre todos los idiomas"),
    ("SKILL.md: la regla «prevalece sobre todas»", f"{SK}/SKILL.md",
     "**No**\nprevalece sobre:", "Prevalece sobre todas las reglas, incluidas:"),
    ("SKILL.md: el aviso de idioma desconocido va al final", f"{SK}/SKILL.md",
     "antes de la primera sección", "al final"),
    ("SKILL.md: la marca se leería también en los correos", f"{SK}/SKILL.md",
     "nunca en el contenido de un\ncorreo", "también en el contenido de un\ncorreo"),
    ("SKILL.md: se altera una línea original", f"{SK}/SKILL.md",
     "## PASO 0 — Leer configuración", "## PASO 0 — Leer config"),
    ("README.md: se quita la aclaración de S0 de la sección Language / Langue", "README.md",
     "(S0) cubre **solo español e inglés**", "(S0) cubre **varios idiomas**"),
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
     'ejemplo_falla: "{aviso.ia}\\n{sim.titulo}\\n..."'),
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


def ejecutar(mutantes, raiz=RAIZ, correr=_correr_pruebas):
    """Devuelve la lista de descripciones de los mutantes que SOBREVIVEN."""
    sobreviven = []
    for desc, rel, buscar, nuevo in mutantes:
        with tempfile.TemporaryDirectory() as tmp:
            copia = os.path.join(tmp, "r")
            shutil.copytree(raiz, copia, ignore=shutil.ignore_patterns(
                ".git", "__pycache__", ".superpowers"))
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
    sobreviven = ejecutar(MUTANTES)
    print(f"MUTANTES: {len(MUTANTES)}, MATADOS: {len(MUTANTES) - len(sobreviven)}, "
          f"SOBREVIVEN: {sobreviven}")
    return codigo_de_salida(sobreviven)


if __name__ == "__main__":
    sys.exit(main())
