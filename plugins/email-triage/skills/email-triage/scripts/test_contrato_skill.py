"""Gate de deriva doc<->codigo (NO1, auditoria 2026-07-17).

El codigo ya no confia en el modelo (escapado, scoring, locks son mecanismo),
pero el SKILL.md si confia en que sus invocaciones a triage_helpers.py
(subcomando + flags) sigan existiendo tal cual en el argparse real. Este test
extrae todas las invocaciones mencionadas en la doctrina (SKILL.md,
references/*.md, commands/triage.md, y el propio docstring del modulo) y las
valida contra la superficie real de _construir_parser(): coherencia
doc<->codigo como mecanismo, no como disciplina.
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


if __name__ == "__main__":
    unittest.main()
