#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# fix-cowork-version.sh
# Actualiza los archivos del email-triage en el rpm de Cowork
# Y en la caché de Claude Code con la versión correcta del repo local.
# Ejecutar después de cada reinstalación o actualización.
# Solo compatible con macOS (requiere Cowork y Claude Code para macOS).
# ═══════════════════════════════════════════════════════════════

VERSION="3.0.1"
REPO="$HOME/email-triage-plugin/plugins/email-triage"
SESSION_BASE="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"
CLAUDE_CACHE="$HOME/.claude/plugins/cache/email-triage-plugin/email-triage/$VERSION"

echo "=== Fix email-triage version v$VERSION ==="

# ── Verificar plataforma (solo macOS) ────────────────────────────
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "⚠️  Advertencia: este script está diseñado para macOS."
  echo "   Cowork y Claude Code (desktop) solo están disponibles en macOS."
  echo "   Continuando de todas formas para la caché de Claude Code CLI..."
fi

# ── Validar que el repo local existe ─────────────────────────────
if [ ! -d "$REPO" ]; then
  echo "❌ Error: no se encuentra el repo local en $REPO"
  echo "   Clona el repo primero: git clone https://github.com/novanoticia/email-triage-plugin ~/email-triage-plugin"
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
      if python3 -c "
import json, sys
with open(sys.argv[1]) as fh:
    d = json.load(fh)
sys.exit(0 if d.get('name') == 'email-triage' else 1)
" "$file" 2>/dev/null; then
        RPM_PLUGIN="$(dirname "$(dirname "$file")")"
        break
      fi
    fi
  done < <(find "$SESSION_BASE" -name "plugin.json" -print0 2>/dev/null)
fi

if [ -n "$RPM_PLUGIN" ]; then
  # Crear directorios destino si no existen
  mkdir -p "$RPM_PLUGIN/.claude-plugin"
  mkdir -p "$RPM_PLUGIN/skills/email-triage"

  cp "$REPO/.claude-plugin/plugin.json"      "$RPM_PLUGIN/.claude-plugin/plugin.json" && \
  cp "$REPO/skills/email-triage/SKILL.md"    "$RPM_PLUGIN/skills/email-triage/SKILL.md" && \
  cp "$REPO/skills/email-triage/config.yaml" "$RPM_PLUGIN/skills/email-triage/config.yaml" && \
  echo "✅ Cowork (rpm): actualizado a v$VERSION" || \
  echo "❌ Error al copiar archivos a Cowork rpm"
else
  echo "⚠️  Cowork: plugin no encontrado en rpm (¿está instalado en Cowork?)"
fi

# ── 2. CLAUDE CODE (caché) ────────────────────────────────────────
# Limpiar caché de versiones anteriores si existen
CACHE_PARENT="$(dirname "$CLAUDE_CACHE")"
if [ -d "$CACHE_PARENT" ]; then
  for old_version in "$CACHE_PARENT"/*/; do
    # Guard: skip if the glob matched a literal unexpanded pattern (no directories found)
    [ -d "$old_version" ] || continue
    # Guard: only remove directories directly inside CACHE_PARENT, never empty paths
    old_basename="$(basename "$old_version")"
    if [ -n "$old_basename" ] && [ "$old_version" != "$CLAUDE_CACHE/" ]; then
      echo "🧹 Limpiando caché antigua: $old_basename"
      rm -rf "$old_version"
    fi
  done
fi

mkdir -p "$CLAUDE_CACHE"
cp -r "$REPO/." "$CLAUDE_CACHE/" && \
echo "✅ Claude Code (caché): actualizado a v$VERSION" || \
echo "❌ Error al copiar archivos a caché de Claude Code"

echo ""
echo "Reinicia Cowork y Claude Code para que tomen los cambios."
