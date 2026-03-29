#!/bin/bash
# Actualiza los archivos del email-triage en el rpm de Cowork
# con la versión correcta del repo local.
# Ejecutar después de cada reinstalación en Cowork.

REPO="$HOME/email-triage-plugin/plugins/email-triage"
SESSION_BASE="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"

# Buscar plugin.json de email-triage dentro de rpm
RPM_PLUGIN_JSON=""
while IFS= read -r -d '' file; do
  if [[ "$file" == */rpm/* ]]; then
    if python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('name')=='email-triage' else 1)" "$file" 2>/dev/null; then
      RPM_PLUGIN_JSON="$file"
      break
    fi
  fi
done < <(find "$SESSION_BASE" -name "plugin.json" -print0 2>/dev/null)

if [ -z "$RPM_PLUGIN_JSON" ]; then
  echo "❌ No se encontró email-triage en el rpm de Cowork."
  echo "   Asegúrate de que el plugin está instalado antes de ejecutar este script."
  exit 1
fi

# El plugin root es dos niveles arriba de plugin.json (.claude-plugin/plugin.json)
RPM_PLUGIN="$(dirname "$(dirname "$RPM_PLUGIN_JSON")")"
echo "📁 Plugin encontrado: $RPM_PLUGIN"

cp "$REPO/.claude-plugin/plugin.json"              "$RPM_PLUGIN/.claude-plugin/plugin.json"
cp "$REPO/skills/email-triage/SKILL.md"            "$RPM_PLUGIN/skills/email-triage/SKILL.md"
cp "$REPO/skills/email-triage/config.yaml"         "$RPM_PLUGIN/skills/email-triage/config.yaml"

VERSION=$(python3 -c "import json; print(json.load(open('$RPM_PLUGIN/.claude-plugin/plugin.json'))['version'])" 2>/dev/null)
echo "✅ Actualizado a v$VERSION"
echo "   Reinicia Cowork para que tome los cambios."
