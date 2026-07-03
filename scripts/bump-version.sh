#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# bump-version.sh X.Y.Z — sube la versión del plugin en TODOS los
# sitios de una sola pasada y valida con el mismo gate que el CI.
# (Resuelve el issue #5: el bump manual derivaba — el título del
# README se quedó en v3.3 durante todo v3.4, y el H1 del SKILL.md
# seguía en v3.4 en un plugin v3.8.)
#
# La versión vive en 7 lugares:
#   Semver completo X.Y.Z (lo valida el gate de CI):
#     1. .claude-plugin/plugin.json
#     2. plugins/email-triage/.claude-plugin/plugin.json
#     3. .claude-plugin/marketplace.json
#     4. frontmatter `version:` de SKILL.md
#     5. H1 del README.md              (# Email Triage Plugin vX.Y.Z)
#   Major.minor X.Y (documentales):
#     6. cabecera de config.yaml       (EMAIL TRIAGE vX.Y)
#     7. H1 del SKILL.md               (# Email Triage vX.Y —)
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

# sed -i portable (BSD/macOS y GNU): sufijo de backup y borrado posterior.
sedi() { sed -i.bak "$1" "$2" && rm -f "$2.bak"; }

# 1-3: los tres JSON — solo la línea "version".
for f in .claude-plugin/plugin.json \
         plugins/email-triage/.claude-plugin/plugin.json \
         .claude-plugin/marketplace.json; do
  sedi "s/\"version\": \"[0-9][0-9.]*\"/\"version\": \"$NEW\"/" "$f"
done

# 4: frontmatter del SKILL.
sedi "s/^version: \"[0-9][0-9.]*\"/version: \"$NEW\"/" "$SKILL"

# 5: H1 del README.
sedi "s/^# Email Triage Plugin v[0-9][0-9.]*/# Email Triage Plugin v$NEW/" README.md

# 6: cabecera de config (major.minor).
sedi "s/EMAIL TRIAGE v[0-9][0-9.]*/EMAIL TRIAGE v$MM/" "$CONFIG"

# 7: H1 del SKILL (major.minor).
sedi "s/^# Email Triage v[0-9][0-9.]* —/# Email Triage v$MM —/" "$SKILL"

echo "✅ Versión fijada a v$NEW (config/H1 a v$MM) en 7 sitios."

# Validar con el MISMO criterio que el gate de CI, para no depender de
# que el push llegue rojo si algún sed no casó (p. ej. formato inesperado).
python3 - "$NEW" "$MM" <<'PY'
import json, re, sys, pathlib
new, mm = sys.argv[1], sys.argv[2]
r = pathlib.Path('.')
def jver(p): return json.loads((r/p).read_text(encoding='utf-8'))['version']
vals = {
  'plugin(root)': jver('.claude-plugin/plugin.json'),
  'plugin(inner)': jver('plugins/email-triage/.claude-plugin/plugin.json'),
  'marketplace': re.search(r'"version"\s*:\s*"([^"]+)"',
      (r/'.claude-plugin/marketplace.json').read_text(encoding='utf-8')).group(1),
  'SKILL frontmatter': re.search(r'(?m)^version:\s*"?([0-9.]+)"?',
      (r/'plugins/email-triage/skills/email-triage/SKILL.md').read_text(encoding='utf-8')).group(1),
  'README H1': re.search(r'(?m)^#\s+Email Triage Plugin v([0-9.]+)',
      (r/'README.md').read_text(encoding='utf-8')).group(1),
}
bad = {k: v for k, v in vals.items() if v != new}
assert not bad, f"semver no coincide con {new}: {bad}"
skill = (r/'plugins/email-triage/skills/email-triage/SKILL.md').read_text(encoding='utf-8')
h1 = re.search(r'(?m)^#\s+Email Triage v([0-9.]+)\s+—', skill).group(1)
assert h1 == mm, f"H1 del SKILL v{h1} != v{mm}"
cfg = (r/'plugins/email-triage/skills/email-triage/config.yaml').read_text(encoding='utf-8')
ch = re.search(r'EMAIL TRIAGE v([0-9.]+)', cfg).group(1)
assert ch == mm, f"cabecera de config v{ch} != v{mm}"
print(f"✅ Coherencia OK: semver v{new} (5 sitios) · major.minor v{mm} (H1 + config)")
PY

echo ""
echo "Siguiente: revisa 'git diff', añade la entrada de changelog en README.md"
echo "y corre los tests antes de commit/tag."
