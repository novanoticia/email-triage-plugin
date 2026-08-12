"""Bootstrap de la suite.

Los tests viven FUERA de la skill a propósito: `skills/email-triage/scripts/`
se empaqueta entero al exportar al estándar Agent Skills, y 217 KB de tests
viajaban dentro de cada `.zip` sin aportar nada al agente de destino (y
disparando hallazgos de seguridad por los payloads de ataque que usan como
fixtures).

Como ya no comparten directorio con el código bajo prueba, hay que poner
`scripts/` en `sys.path` antes de que los módulos de test hagan
`import triage_helpers`. Este `__init__` se ejecuta al importar el paquete
`tests`, o sea antes que cualquier test, siempre que se descubra con
`-t .` (ver .github/workflows/tests.yml).
"""
import os
import sys

DIR_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "plugins", "email-triage", "skills", "email-triage", "scripts",
)

if DIR_SCRIPTS not in sys.path:
    sys.path.insert(0, DIR_SCRIPTS)
