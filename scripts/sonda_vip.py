#!/usr/bin/env python3
"""Sonda de la fase 0 de docs/diseno-historiales.md: ¿expone Mail.app sus VIP?

Herramienta de desarrollo (no se distribuye con el plugin). Se ejecuta UNA vez
en el Mac del mantenedor para decidir si los VIP de Mail pueden ser una fuente
de «remitentes importantes» o si se descartan y queda solo «Archivados».

Prueba tres vías, de la más limpia a la más frágil:

1. **Diccionario AppleScript** (`sdef` de Mail.app): ¿hay algún término con
   «VIP»? Imprime los términos del diccionario, que son de Apple, no tuyos.
2. **Buzones con «VIP» en el nombre**, vistos desde AppleScript. El recuento se
   hace dentro de AppleScript: los nombres de tus buzones no llegan a Python.
3. **Ficheros de datos de Mail** (`~/Library/Mail/V*/MailData` y las
   preferencias de Mail) cuyo nombre o claves mencionen «VIP». Cuenta cuántas
   cadenas con forma de dirección contienen (y cuántas bajo una clave «VIP»);
   NUNCA las imprime.

Garantías: no escribe nada, no envía nada a ninguna red ni API, no imprime
direcciones, asuntos ni nombres de buzones. Solo recuentos, rutas de ficheros
con «vip» en el nombre y términos del diccionario de Apple. Uso:

    python3 scripts/sonda_vip.py

La vía 2 abre Mail.app si está cerrado, y macOS puede pedir permiso para que
Terminal controle Mail. La vía 3 puede necesitar «Acceso total al disco»; sin
él informa «sin permiso» y sigue.
"""
import os
import plistlib
import re
import subprocess
import sys

MAIL_APP = ("/System/Applications/Mail.app", "/Applications/Mail.app")
MAX_PLIST_BYTES = 20 * 2**20
SIN_PERMISO = "sin permiso (¿Acceso total al disco?)"
_DIRECCION = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
_VIP = re.compile(r"vip", re.IGNORECASE)

# Cuenta buzones con «VIP» en el nombre sin devolver ningún nombre.
APPLESCRIPT_BUZONES = '''
tell application "Mail"
    set n to 0
    try
        set n to n + (count of (every mailbox whose name contains "VIP"))
    end try
    repeat with a in accounts
        try
            set n to n + (count of (every mailbox of a whose name contains "VIP"))
        end try
    end repeat
    return n
end tell
'''


def terminos_vip(sdef_xml):
    """Términos del diccionario (atributo name=) que contienen «vip». Pura."""
    nombres = re.findall(r'\bname="([^"]*)"', sdef_xml)
    return sorted({n for n in nombres if _VIP.search(n)})


def contar_en_plist(obj):
    """(direcciones, bajo_vip, claves_vip) en un plist ya parseado.

    `direcciones`: cadenas distintas con forma de dirección en todo el fichero;
    `bajo_vip`: las que cuelgan de una clave con «VIP» (en las preferencias de
    Mail hay otras direcciones, como las de tus cuentas, que no son VIP);
    `claves_vip`: claves que contienen «VIP». Devuelve solo números: las
    direcciones nunca salen de esta función."""
    todas, vip, claves = set(), set(), 0
    pila = [(obj, False)]
    while pila:
        x, en_vip = pila.pop()
        if isinstance(x, dict):
            for k, v in x.items():
                es_vip = isinstance(k, str) and bool(_VIP.search(k))
                claves += es_vip
                pila.append((v, en_vip or es_vip))
        elif isinstance(x, (list, tuple)):
            pila.extend((e, en_vip) for e in x)
        elif isinstance(x, str) and _DIRECCION.match(x.strip()):
            d = x.strip().lower()
            todas.add(d)
            if en_vip:
                vip.add(d)
    return len(todas), len(vip), claves


def _leer_plist(ruta):
    """(objeto, motivo). Motivo no vacío si no se pudo leer."""
    try:
        if os.path.getsize(ruta) > MAX_PLIST_BYTES:
            return None, "demasiado grande"
        with open(ruta, "rb") as fh:
            return plistlib.load(fh), ""
    except PermissionError:
        return None, SIN_PERMISO
    except Exception:  # plist corrupto o formato inesperado: no se interpreta
        return None, "no es un plist legible"


def candidatos(home):
    """Ficheros a mirar: los de MailData con «vip» en el nombre y las
    preferencias de Mail (donde se buscan claves con «VIP»).

    Un directorio sin permiso se devuelve con su motivo en vez de omitirse:
    `glob` y `os.path.exists` se tragan el PermissionError, y la sonda diría
    «ninguno encontrado» cuando en realidad no pudo mirar (revisión de Codex,
    PR #184)."""
    rutas = []
    mail = os.path.join(home, "Library/Mail")
    try:
        versiones = sorted(n for n in os.listdir(mail) if re.match(r"^V\d+$", n))
    except FileNotFoundError:
        versiones = []
    except OSError:
        rutas.append((mail, SIN_PERMISO))
        versiones = []
    for v in versiones:
        d = os.path.join(mail, v, "MailData")
        try:
            nombres = os.listdir(d)
        except FileNotFoundError:
            continue
        except OSError:
            rutas.append((d, SIN_PERMISO))
            continue
        rutas.extend((os.path.join(d, n), "") for n in sorted(nombres) if _VIP.search(n))
    for p in ("Library/Containers/com.apple.mail/Data/Library/Preferences/com.apple.mail.plist",
              "Library/Preferences/com.apple.mail.plist"):
        ruta = os.path.join(home, p)
        try:
            os.stat(ruta)
        except FileNotFoundError:
            continue
        except OSError:
            rutas.append((ruta, SIN_PERMISO))
            continue
        rutas.append((ruta, ""))
    return rutas


def _ejecutar(cmd, entrada=None):
    try:
        r = subprocess.run(cmd, input=entrada, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", type(e).__name__


def _corta(ruta, home):
    return "~" + ruta[len(home):] if ruta.startswith(home) else ruta


def main():
    if sys.platform != "darwin":
        print("Esta sonda solo tiene sentido en macOS (Mail.app).")
        return 2
    home = os.path.expanduser("~")
    print("Sonda VIP de Mail.app: solo recuentos, no imprime direcciones ni asuntos.\n")

    print("1) Diccionario AppleScript de Mail.app")
    app = next((a for a in MAIL_APP if os.path.isdir(a)), None)
    if not app:
        print("   Mail.app no encontrado.")
    else:
        rc, out, _ = _ejecutar(["sdef", app])
        if rc != 0:
            print("   sdef falló (código %s)." % rc)
        else:
            t = terminos_vip(out)
            print("   términos con «VIP»: %s" % (", ".join(t) if t else "ninguno"))

    print("2) Buzones con «VIP» en el nombre (vía AppleScript)")
    rc, out, err = _ejecutar(["osascript", "-"], APPLESCRIPT_BUZONES)
    if rc == 0 and out.strip().isdigit():
        print("   buzones: %s" % out.strip())
    else:
        # No se imprime stderr entero: podría citar nombres; solo su código.
        codigo = re.search(r"\((-?\d+)\)", err or "")
        print("   no se pudo consultar (error %s). ¿Permiso de Automatización?"
              % (codigo.group(1) if codigo else rc))

    print("3) Ficheros de datos de Mail")
    rutas = candidatos(home)
    if not rutas:
        print("   ninguno encontrado.")
    for ruta, motivo in rutas:
        if not motivo and os.path.isfile(ruta):
            obj, motivo = _leer_plist(ruta)
        if motivo:
            print("   %s: %s" % (_corta(ruta, home), motivo))
            continue
        if not os.path.isfile(ruta):
            print("   %s: es un directorio, no se lee" % _corta(ruta, home))
            continue
        n_dir, n_vip, n_claves = contar_en_plist(obj)
        print("   %s: %d direcciones (%d bajo una clave «VIP»), %d claves con «VIP»"
              % (_corta(ruta, home), n_dir, n_vip, n_claves))

    print("\nCópiame esta salida tal cual: no contiene datos personales.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
