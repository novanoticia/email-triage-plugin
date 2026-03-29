#!/bin/bash
# Actualiza los archivos del email-triage en el rpm de Cowork Y en la caché de Claude Code
# con la versión correcta del repo local.
# Ejecutar después de cada reinstalación.

REPO="$HOME/email-triage-plugin/plugins/email-triage"
SESSION_BASE="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"
CLAUDE_CACHE="$HOME/.claude/plugins/cache/email-triage-plugin/email-triage/3.0.0"

echo "=== Fix email-triage version ==="

# ── 1. COWORK (rpm) ──────────────────────────────────────────────
RPM_PLUGIN=""
while IFS= read -r -d '' file; do
  if [[ "$file" == */rpm/* ]]; then
    if python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('name')=='email-triage' else 1)" "$file" 2>/dev/null; then
      RPM_PLUGIN="$(dirname "$(dirname "$file")")"
      break
    fi
  fi
done < <(find "$SESSION_BASE" -name "plugin.json" -print0 2>/dev/null)

if [ -n "$RPM_PLUGIN" ]; then
  cp "$REPO/.claude-plugin/plugin.json"     "$RPM_PLUGIN/.claude-plugin/plugin.json"
  cp "$REPO/skills/email-triage/SKILL.md"   "$RPM_PLUGIN/skills/email-triage/SKILL.md"
  cp "$REPO/skills/email-triage/config.yaml" "$RPM_PLUGIN/skills/email-triage/config.yaml"
  echo "✅ Cowork (rpm): actualizado a v3.0.0"
else
  echo "⚠️  Cowork: plugin no encontrado en rpm (¿está instalado?)"
fi

# ── 2. CLAUDE CODE (caché) ────────────────────────────────────────
mkdir -p "$CLAUDE_CACHE"
cp -r "$REPO/." "$CLAUDE_CACHE/"
echo "✅ Claude Code (caché): actualizado a v3.0.0"

echo ""
echo "Reinicia Cowork y Claude Code para que tomen los cambios."
