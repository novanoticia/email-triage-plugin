#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# fix-cowork-version.sh
# Actualiza los archivos del email-triage en el rpm de Cowork
# Y en la caché de Claude Code con la versión correcta del repo local.
# Ejecutar después de cada reinstalación o actualización.
# ═══════════════════════════════════════════════════════════════

# Deriva la ruta del plugin desde la ubicación del propio script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$SCRIPT_DIR/plugins/email-triage"
SESSION_BASE="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"

# Leer VERSION dinámicamente desde plugin.json (fuente única de verdad)
PLUGIN_JSON="$REPO/.claude-plugin/plugin.json"
if [ ! -f "$PLUGIN_JSON" ]; then
  echo "❌ Error: no se encuentra $PLUGIN_JSON"
  echo "   Ejecuta este script desde dentro del repo clonado."
  exit 1
fi
VERSION=$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON'))['version'])" 2>/dev/null || true)
if [ -z "$VERSION" ]; then
  echo "❌ Error: no se pudo leer 'version' de $PLUGIN_JSON"
  exit 1
fi

# Coherencia de versiones: plugin.json es la fuente de verdad, pero el
# frontmatter del SKILL.md no debe contradecirla (genera confusión al depurar).
SKILL_VERSION=$(grep -m1 '^version:' "$REPO/skills/email-triage/SKILL.md" | sed 's/version:[[:space:]]*"\{0,1\}\([0-9.]*\)"\{0,1\}.*/\1/' || true)
if [ -n "$SKILL_VERSION" ] && [ "$SKILL_VERSION" != "$VERSION" ]; then
  echo "⚠️  Deriva de versiones: plugin.json=v$VERSION pero SKILL.md=v$SKILL_VERSION"
  echo "   Sincroniza el frontmatter de SKILL.md antes del próximo release."
fi

CLAUDE_CACHE="$HOME/.claude/plugins/cache/email-triage-plugin/email-triage/$VERSION"

echo "=== Fix email-triage version v$VERSION ==="
echo "   Repo: $SCRIPT_DIR"

# ── Validar que el repo local existe ─────────────────────────────
if [ ! -d "$REPO" ]; then
  echo "❌ Error: no se encuentra la carpeta plugins/email-triage en $SCRIPT_DIR"
  echo "   Asegúrate de ejecutar el script desde dentro del repo clonado."
  exit 1
fi

if [ ! -f "$REPO/skills/email-triage/SKILL.md" ]; then
  echo "❌ Error: SKILL.md no encontrado en $REPO/skills/email-triage/"
  echo "   El repo parece incompleto o con estructura diferente."
  exit 1
fi

# ── Validar que los archivos fuente son legibles ─────────────────
for f in "$REPO/.claude-plugin/plugin.json" "$REPO/skills/email-triage/SKILL.md" "$REPO/skills/email-triage/config.yaml"; do
  if [ ! -r "$f" ]; then
    echo "❌ Error: no se puede leer $f"
    exit 1
  fi
done

# ── 1. COWORK (rpm) ──────────────────────────────────────────────
RPM_PLUGIN=""
if [ -d "$SESSION_BASE" ]; then
  while IFS= read -r -d '' file; do
    if [[ "$file" == */rpm/* ]]; then
      if python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('name')=='email-triage' else 1)" "$file" 2>/dev/null; then
        RPM_PLUGIN="$(dirname "$(dirname "$file")")"
        break
      fi
    fi
  done < <(find "$SESSION_BASE" -name "plugin.json" -print0 2>/dev/null)
fi

if [ -n "$RPM_PLUGIN" ]; then
  # Copiar el ÁRBOL COMPLETO del plugin, no archivos sueltos. Hasta
  # v3.4.1 solo se copiaban plugin.json, SKILL.md y config.yaml, así
  # que ni scripts/triage_helpers.py ni references/ ni commands/
  # llegaban a Cowork: en esa plataforma no existía la "vía preferente"
  # de v3.4 ni el fallback manual documentado. Copiar el árbol evita
  # además olvidar archivos que se añadan en versiones futuras.
  mkdir -p "$RPM_PLUGIN"
  cp -r "$REPO/." "$RPM_PLUGIN/" && \
  echo "✅ Cowork (rpm): árbol completo del plugin actualizado a v$VERSION" || \
  echo "❌ Error al copiar archivos a Cowork rpm"
else
  echo "⚠️  Cowork: plugin no encontrado en rpm (¿está instalado en Cowork?)"
fi

# ── 2. CLAUDE CODE (caché) ────────────────────────────────────────
# Limpiar caché de versiones anteriores si existen
CACHE_PARENT="$(dirname "$CLAUDE_CACHE")"
if [ -d "$CACHE_PARENT" ]; then
  for old_version in "$CACHE_PARENT"/*/; do
    if [ "$old_version" != "$CLAUDE_CACHE/" ] && [ -d "$old_version" ]; then
      echo "🧹 Limpiando caché antigua: $(basename "$old_version")"
      rm -rf "$old_version"
    fi
  done
fi

mkdir -p "$CLAUDE_CACHE"
cp -r "$REPO/." "$CLAUDE_CACHE/" && \
echo "✅ Claude Code (caché): actualizado a v$VERSION" || \
echo "❌ Error al copiar archivos a caché de Claude Code"

# ── 3. GENERAR ZIP PARA COWORK (opcional) ─────────────────────────
# Si se pasa --zip, genera el zip con la estructura correcta para
# instalación manual en Cowork (sin el envoltorio del repo).
if [[ "${1:-}" == "--zip" ]]; then
  ZIP_NAME="email-triage-v${VERSION}.zip"
  ZIP_PATH="$(dirname "$REPO")/../$ZIP_NAME"
  (cd "$REPO" && zip -r "$ZIP_PATH" . -x "*.DS_Store") && \
  echo "📦 Zip generado: $ZIP_PATH" && \
  echo "   Estructura: .claude-plugin/, skills/, .mcp.json (raíz del plugin)" || \
  echo "❌ Error al generar zip"
fi

echo ""
echo "Reinicia Cowork y Claude Code para que tomen los cambios."
