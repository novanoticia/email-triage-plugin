#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# install-plugin.sh — email-triage-plugin
# Instalación / actualización automática para macOS
#
# Flujo:
#   1. Verifica dependencias (git, python3).
#   2. Clona (o actualiza con fetch + reset) el marketplace en la
#      ruta correcta que Claude Code/Cowork esperan:
#        ~/.claude/plugins/marketplaces/email-triage-plugin/
#   3. Lee la versión dinámicamente desde plugin.json.
#   4. Ejecuta fix-cowork-version.sh para sincronizar el plugin
#      con la caché de Claude Code y con el rpm de Cowork.
#   5. Crea ~/.email-triage/ para logs de sesión y telemetría.
#   6. Imprime instrucciones claras de siguiente paso.
# ═══════════════════════════════════════════════════════════════

PLUGIN_NAME="email-triage"
GITHUB_REPO="novanoticia/email-triage-plugin"
BRANCH="main"
MARKETPLACE_DIR="$HOME/.claude/plugins/marketplaces/email-triage-plugin"
TELEMETRY_DIR="$HOME/.email-triage"

echo "🚀 Instalando/actualizando '$PLUGIN_NAME'..."
echo "   Destino: $MARKETPLACE_DIR"
echo ""

# ── 1. Verificar dependencias ──────────────────────────────────
missing_deps=()
for cmd in git python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing_deps+=("$cmd")
  fi
done

if [ ${#missing_deps[@]} -gt 0 ]; then
  echo "❌ Faltan dependencias: ${missing_deps[*]}"
  echo "   Instálalas y vuelve a ejecutar este script."
  echo "   En macOS con Homebrew: brew install ${missing_deps[*]}"
  exit 1
fi

# ── 2. Clonar o actualizar el repo ─────────────────────────────
mkdir -p "$(dirname "$MARKETPLACE_DIR")"

if [ -d "$MARKETPLACE_DIR/.git" ]; then
  echo "📥 Repo existente detectado. Actualizando (fetch + reset a origin/$BRANCH)..."

  # ── 2-pre. Rescatar config personalizado (migración v3.3 → v3.4+) ──
  # En v3.3 el config del usuario vivía DENTRO del repo; el reset --hard
  # de abajo lo destruiría sin aviso. Si todavía no existe el config
  # personal de v3.4+ y el del repo difiere de su plantilla original
  # (HEAD local), rescatarlo ANTES de tocar nada.
  RESCATE_USER_CONFIG="$TELEMETRY_DIR/config.yaml"
  RESCATE_REPO_CONFIG="plugins/$PLUGIN_NAME/skills/$PLUGIN_NAME/config.yaml"
  if [ ! -f "$RESCATE_USER_CONFIG" ] && [ -f "$MARKETPLACE_DIR/$RESCATE_REPO_CONFIG" ]; then
    if ! git -C "$MARKETPLACE_DIR" diff HEAD --quiet -- "$RESCATE_REPO_CONFIG" 2>/dev/null; then
      mkdir -p "$TELEMETRY_DIR"
      cp "$MARKETPLACE_DIR/$RESCATE_REPO_CONFIG" "$RESCATE_USER_CONFIG"
      echo "🛟 Config personalizado detectado en el repo (formato v3.3)."
      echo "   Rescatado a: $RESCATE_USER_CONFIG"
      echo "   (sobrevivirá a esta y a todas las actualizaciones futuras)"
    fi
  fi

  if ! git -C "$MARKETPLACE_DIR" fetch origin "$BRANCH" 2>&1; then
    echo "❌ Error al hacer fetch del repositorio."
    exit 1
  fi
  # Resetear a origin/main para garantizar estado limpio
  if ! git -C "$MARKETPLACE_DIR" reset --hard "origin/$BRANCH" 2>&1; then
    echo "❌ Error al resetear a origin/$BRANCH."
    exit 1
  fi
  echo "✅ Repo actualizado a origin/$BRANCH"
else
  echo "📦 Clonando repositorio..."
  if ! git clone --branch "$BRANCH" "https://github.com/$GITHUB_REPO.git" "$MARKETPLACE_DIR"; then
    echo "❌ Error al clonar el repositorio."
    exit 1
  fi
  echo "✅ Repo clonado"
fi

# ── 3. Leer versión dinámicamente desde plugin.json ────────────
PLUGIN_JSON="$MARKETPLACE_DIR/plugins/$PLUGIN_NAME/.claude-plugin/plugin.json"
if [ ! -f "$PLUGIN_JSON" ]; then
  echo "❌ No se encuentra $PLUGIN_JSON"
  echo "   La estructura del repo es inesperada."
  exit 1
fi

VERSION=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$PLUGIN_JSON" 2>/dev/null || true)
if [ -z "$VERSION" ]; then
  echo "❌ No se pudo leer la versión desde $PLUGIN_JSON"
  exit 1
fi
echo "📋 Versión detectada: v$VERSION"

# ── 4. Ejecutar fix-cowork-version.sh ──────────────────────────
FIX_SCRIPT="$MARKETPLACE_DIR/fix-cowork-version.sh"
if [ -f "$FIX_SCRIPT" ]; then
  echo ""
  echo "🔧 Sincronizando con Claude Code y Cowork..."
  chmod +x "$FIX_SCRIPT"
  if "$FIX_SCRIPT"; then
    echo "✅ Sincronización completada"
  else
    echo "⚠️  fix-cowork-version.sh devolvió errores (revísalos arriba)"
  fi
else
  echo "⚠️  fix-cowork-version.sh no encontrado — omitiendo sync"
fi

# ── 5. Crear directorio de telemetría/sesión ───────────────────
# Contiene metadatos de correo (asuntos, remitentes) en JSONL con retención
# indefinida, así que se fija a 700: solo el dueño puede leerlo. Se aplica
# SIEMPRE (mkdir + chmod), también sobre directorios preexistentes creados
# por versiones anteriores sin permisos restrictivos.
if [ ! -d "$TELEMETRY_DIR" ]; then
  # 700 desde el propio mkdir: cierra la ventana entre crear y chmod en la
  # que el directorio quedaría con los permisos del umask (world-readable).
  mkdir -p -m 700 "$TELEMETRY_DIR"
  echo "📂 Creado: $TELEMETRY_DIR (para session logs y telemetría)"
fi
chmod 700 "$TELEMETRY_DIR" 2>/dev/null \
  && echo "🔒 Permisos de $TELEMETRY_DIR fijados a 700 (solo el dueño)" \
  || echo "⚠️  No se pudieron fijar permisos 700 en $TELEMETRY_DIR (revísalo a mano)"

# ── 5b. Config personal persistente (NUEVO en v3.4) ────────────
# El config del usuario vive FUERA del repo para sobrevivir a
# `git reset --hard` en actualizaciones y no acabar en git.
USER_CONFIG="$TELEMETRY_DIR/config.yaml"
TEMPLATE_CONFIG="$MARKETPLACE_DIR/plugins/$PLUGIN_NAME/skills/$PLUGIN_NAME/config.yaml"
if [ -f "$USER_CONFIG" ]; then
  echo "🔒 Config personal preservado: $USER_CONFIG (no se ha tocado)"
else
  cp "$TEMPLATE_CONFIG" "$USER_CONFIG"
  echo "📝 Creado config personal desde plantilla: $USER_CONFIG"
fi

# ── 6. Mensaje final ───────────────────────────────────────────
echo ""
echo "🎉 Instalación de $PLUGIN_NAME v$VERSION completada."
echo ""
echo "Siguientes pasos:"
echo "  1. Edita tu config personal (sobrevive a las actualizaciones):"
echo "     $USER_CONFIG"
echo "     (rellena usuario.nombre, usuario.perfil, correo.cuenta, carpetas)"
echo "     ⚠️  NO edites el config.yaml de dentro del repo: es solo la"
echo "     plantilla y se sobrescribe en cada actualización."
echo ""
echo "  2. Reinicia Claude Code y/o Cowork."
echo ""
echo "  3. En Cowork: si ya tenías el plugin activo, desactívalo y vuelve"
echo "     a activarlo para que cargue la versión nueva."
echo ""
echo "  4. Primera vez: activa el skill con '/email-triage' o pide"
echo "     al agente 'filtra mi correo' / 'revisa mi bandeja'."
echo ""
