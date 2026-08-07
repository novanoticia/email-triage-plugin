#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# bump-version.sh X.Y.Z — sube la versión del plugin en TODOS los
# sitios de una sola pasada y valida con el mismo gate que el CI.
# (Resuelve el issue #5: el bump manual derivaba — el título del
# README se quedó en v3.3 durante todo v3.4, y el H1 del SKILL.md
# seguía en v3.4 en un plugin v3.8.)
#
# La versión vive en 9 lugares:
#   Semver completo X.Y.Z (lo valida el gate de CI):
#     1. .claude-plugin/plugin.json
#     2. plugins/email-triage/.claude-plugin/plugin.json   (manifiesto Claude)
#     3. plugins/email-triage/plugin.json                  (manifiesto portable
#                                                           Agent Plugins 1.0.0)
#     4. .claude-plugin/marketplace.json
#     5. `metadata.version` del frontmatter de SKILL.md
#     6. H1 del README.md              (# Email Triage Plugin vX.Y.Z)
#     7. docstring de triage_helpers.py (plugin email-triage (vX.Y.Z))
#   Major.minor X.Y (documentales):
#     8. cabecera de config.yaml       (EMAIL TRIAGE vX.Y)
#     9. H1 del SKILL.md               (# Email Triage vX.Y —)
#
# Ojo con el nº 5: `version` NO es una clave permitida en el frontmatter de
# Agent Skills (el conjunto es cerrado: name, description, license,
# compatibility, metadata, allowed-tools), así que vive anidada bajo
# `metadata:`. Si la subes de nivel, un cliente conformante se salta el skill.
#
# Uso:  ./scripts/bump-version.sh 3.8.3
# No hace commit ni tag: deja el árbol listo para que revises el diff,
# añadas el changelog del README y corras los tests.
# ═══════════════════════════════════════════════════════════════

NEW="${1:-}"
if ! [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "❌ Uso: $0 X.Y.Z   (semver, p. ej. 3.8.3)"
  exit 1
fi
MM="${NEW%.*}"   # major.minor

# Raíz del repo = un nivel por encima de este script (scripts/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKILL="plugins/email-triage/skills/email-triage/SKILL.md"
CONFIG="plugins/email-triage/skills/email-triage/config.yaml"
HELPERS="plugins/email-triage/skills/email-triage/scripts/triage_helpers.py"

# sed -i portable (BSD/macOS y GNU): sufijo de backup y borrado posterior.
sedi() { sed -i.bak "$1" "$2" && rm -f "$2.bak"; }

# 1-4: los cuatro JSON — solo la línea "version".
for f in .claude-plugin/plugin.json \
         plugins/email-triage/.claude-plugin/plugin.json \
         plugins/email-triage/plugin.json \
         .claude-plugin/marketplace.json; do
  sedi "s/\"version\": \"[0-9][0-9.]*\"/\"version\": \"$NEW\"/" "$f"
done

# 5: metadata.version del frontmatter del SKILL. La sustitución se acota al
# bloque de frontmatter (1,/^---$/) para no pisar un `  version:` que aparezca
# más abajo en el cuerpo del documento.
sedi "1,/^---$/s/^  version: \"[0-9][0-9.]*\"/  version: \"$NEW\"/" "$SKILL"

# 6: H1 del README.
sedi "s/^# Email Triage Plugin v[0-9][0-9.]*/# Email Triage Plugin v$NEW/" README.md

# 7: docstring de triage_helpers.py. Derivó en silencio (decía v3.8.2 en un
# plugin v3.8.4) porque ni este script ni el CI lo vigilaban.
sedi "s/plugin email-triage (v[0-9][0-9.]*)/plugin email-triage (v$NEW)/" "$HELPERS"

# 8: cabecera de config (major.minor).
sedi "s/EMAIL TRIAGE v[0-9][0-9.]*/EMAIL TRIAGE v$MM/" "$CONFIG"

# 9: H1 del SKILL (major.minor).
sedi "s/^# Email Triage v[0-9][0-9.]* —/# Email Triage v$MM —/" "$SKILL"

echo "✅ Versión fijada a v$NEW (config/H1 a v$MM) en 9 sitios."

# Validar con el MISMO criterio que el gate de CI, para no depender de
# que el push llegue rojo si algún sed no casó (p. ej. formato inesperado).
python3 - "$NEW" "$MM" <<'PY'
import json, re, sys, pathlib
new, mm = sys.argv[1], sys.argv[2]
r = pathlib.Path('.')
def jver(p): return json.loads((r/p).read_text(encoding='utf-8'))['version']
skill_txt = (r/'plugins/email-triage/skills/email-triage/SKILL.md'
             ).read_text(encoding='utf-8')
# El frontmatter se acota antes de buscar: `metadata.version` está indentado y
# un regex suelto podría casar con cualquier `version:` del cuerpo.
fm = re.match(r'\A---\r?\n(.*?)\r?\n---', skill_txt, re.S)
assert fm, "SKILL.md sin bloque de frontmatter YAML al inicio"
vals = {
  'plugin(root)': jver('.claude-plugin/plugin.json'),
  'plugin(inner)': jver('plugins/email-triage/.claude-plugin/plugin.json'),
  'plugin(portable)': jver('plugins/email-triage/plugin.json'),
  'marketplace': re.search(r'"version"\s*:\s*"([^"]+)"',
      (r/'.claude-plugin/marketplace.json').read_text(encoding='utf-8')).group(1),
  'SKILL metadata.version': re.search(r'(?m)^\s+version:\s*"?([0-9.]+)"?',
      fm.group(1)).group(1),
  'README H1': re.search(r'(?m)^#\s+Email Triage Plugin v([0-9.]+)',
      (r/'README.md').read_text(encoding='utf-8')).group(1),
  'helpers docstring': re.search(r'email-triage \(v([0-9.]+)\)',
      (r/'plugins/email-triage/skills/email-triage/scripts/triage_helpers.py'
       ).read_text(encoding='utf-8')).group(1),
}
bad = {k: v for k, v in vals.items() if v != new}
assert not bad, f"semver no coincide con {new}: {bad}"
h1 = re.search(r'(?m)^#\s+Email Triage v([0-9.]+)\s+—', skill_txt).group(1)
assert h1 == mm, f"H1 del SKILL v{h1} != v{mm}"
cfg = (r/'plugins/email-triage/skills/email-triage/config.yaml').read_text(encoding='utf-8')
ch = re.search(r'EMAIL TRIAGE v([0-9.]+)', cfg).group(1)
assert ch == mm, f"cabecera de config v{ch} != v{mm}"
print(f"✅ Coherencia OK: semver v{new} (7 sitios) · major.minor v{mm} (H1 + config)")
PY

echo ""
echo "Siguiente: revisa 'git diff', añade la entrada de changelog en README.md"
echo "y corre los tests antes de commit/tag."
echo ""
echo "📢 Para PUBLICAR el release v$NEW: en GitHub → pestaña 'Actions' → 'release'"
echo "   → botón 'Run workflow'. Crea el tag y la release con notas automáticas"
echo "   (idempotente: si la release ya existe, no hace nada)."
