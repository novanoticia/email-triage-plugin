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

# ── Flags (issue #4) ─────────────────────────────────────────────
# --cowork : parchear también el rpm efímero de Cowork (opt-in). Por defecto
#            NO se toca: la vía canónica en Cowork es el marketplace
#            (.claude-plugin/marketplace.json). El rpm es una ruta de sesión
#            que el usuario no controla y cuyo layout puede cambiar sin aviso.
# --zip    : generar el zip de instalación manual.
# Equivalencia por entorno: PATCH_COWORK_RPM=1 == --cowork (lo usa install).
DO_ZIP=false
DO_COWORK=false
for arg in "$@"; do
  case "$arg" in
    --zip) DO_ZIP=true ;;
    --cowork) DO_COWORK=true ;;
  esac
done
[ "${PATCH_COWORK_RPM:-}" = "1" ] && DO_COWORK=true

# Leer VERSION dinámicamente desde plugin.json (fuente única de verdad)
PLUGIN_JSON="$REPO/.claude-plugin/plugin.json"
if [ ! -f "$PLUGIN_JSON" ]; then
  echo "❌ Error: no se encuentra $PLUGIN_JSON"
  echo "   Ejecuta este script desde dentro del repo clonado."
  exit 1
fi
VERSION=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$PLUGIN_JSON" 2>/dev/null || true)
if [ -z "$VERSION" ]; then
  echo "❌ Error: no se pudo leer 'version' de $PLUGIN_JSON"
  exit 1
fi
# Guarda: 'version' debe ser semver (X.Y.Z) ANTES de construir rutas que mas
# abajo se usan en cp -r y rm -rf. Un valor inesperado no debe llegar a un rm.
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?$ ]]; then
  echo "❌ Error: 'version' no tiene formato semver (X.Y.Z): '$VERSION'"
  exit 1
fi

# Coherencia de versiones: plugin.json es la fuente de verdad, pero el
# frontmatter del SKILL.md no debe contradecirla (genera confusión al depurar).
SKILL_VERSION=$(grep -m1 '^version:' "$REPO/skills/email-triage/SKILL.md" | sed 's/version:[[:space:]]*"\{0,1\}\([0-9.]*\)"\{0,1\}.*/\1/' || true)
if [ -n "$SKILL_VERSION" ] && [ "$SKILL_VERSION" != "$VERSION" ]; then
  echo "⚠️  Deriva de versiones: plugin.json=v$VERSION pero SKILL.md=v$SKILL_VERSION"
  echo "   Sincroniza el frontmatter de SKILL.md antes del próximo release."
fi

# El título del README también declara versión y derivó en el pasado
# (quedó en v3.3.0 durante todo v3.4.0). Mismo aviso, misma fuente de verdad.
README_VERSION=$(grep -m1 '^# Email Triage Plugin v' "$SCRIPT_DIR/README.md" | sed 's/.*v\([0-9.]*\).*/\1/' || true)
if [ -n "$README_VERSION" ] && [ "$README_VERSION" != "$VERSION" ]; then
  echo "⚠️  Deriva de versiones: plugin.json=v$VERSION pero README.md=v$README_VERSION"
  echo "   Actualiza el título del README antes del próximo release."
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

# ── 1. COWORK (rpm) — opt-in (--cowork), ver issue #4 ────────────
# Por defecto NO se parchea el rpm: es una ruta de sesión efímera y la vía
# canónica en Cowork es el marketplace. Con --cowork se fuerza el apaño.
if ! $DO_COWORK; then
  echo "ℹ️  Cowork (rpm): parcheo omitido — vía canónica: marketplace (.claude-plugin/marketplace.json)."
  echo "    Usa --cowork (o PATCH_COWORK_RPM=1) solo si necesitas forzar el rpm de la sesión actual."
else
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

# NOTA (best-effort): parchear el rpm de Cowork por `find` está acoplado a
# la interna de Cowork (rutas de sesión efímeras que pueden cambiar). Es un
# apaño de conveniencia, NO la vía canónica: si Cowork instala el plugin vía
# marketplace, esa ruta es la preferente y este paso sobra. Por eso todo el
# bloque es tolerante a fallo y NUNCA aborta la instalación.
if [ -n "$RPM_PLUGIN" ]; then
  # Guarda ANTES de escribir: `cp -r "$REPO/."` sobre una ruta hallada por
  # `find` en un árbol que no controlamos es peligroso si `find` casó un
  # plugin homónimo o si el layout de Cowork cambió. Confirmar la firma
  # estructural mínima del destino (es la raíz de ESTE plugin) antes del cp.
  if [ ! -f "$RPM_PLUGIN/.claude-plugin/plugin.json" ]; then
    echo "⚠️  Cowork: destino inesperado ($RPM_PLUGIN) sin .claude-plugin/plugin.json — omitido por seguridad"
  elif ! python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('name')=='email-triage' else 1)" "$RPM_PLUGIN/.claude-plugin/plugin.json" 2>/dev/null; then
    echo "⚠️  Cowork: destino ($RPM_PLUGIN) no es el plugin email-triage — omitido por seguridad"
  else
    # Copiar el ÁRBOL COMPLETO del plugin, no archivos sueltos. Hasta
    # v3.4.1 solo se copiaban plugin.json, SKILL.md y config.yaml, así
    # que ni scripts/triage_helpers.py ni references/ ni commands/
    # llegaban a Cowork: en esa plataforma no existía la "vía preferente"
    # de v3.4 ni el fallback manual documentado. Copiar el árbol evita
    # además olvidar archivos que se añadan en versiones futuras.
    if mkdir -p "$RPM_PLUGIN" && cp -r "$REPO/." "$RPM_PLUGIN/"; then
      echo "✅ Cowork (rpm): árbol completo del plugin actualizado a v$VERSION"
    else
      echo "⚠️  Cowork (rpm): no se pudo copiar — best-effort, la instalación continúa"
    fi
  fi
else
  echo "ℹ️  Cowork: plugin no encontrado en rpm (normal si no usas Cowork o si se instala vía marketplace)"
fi
fi   # fin del bloque opt-in --cowork

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
if $DO_ZIP; then
  ZIP_NAME="email-triage-v${VERSION}.zip"
  ZIP_PATH="$(dirname "$REPO")/../$ZIP_NAME"
  (cd "$REPO" && zip -r "$ZIP_PATH" . -x "*.DS_Store") && \
  echo "📦 Zip generado: $ZIP_PATH" && \
  echo "   Estructura: .claude-plugin/, skills/, .mcp.json (raíz del plugin)" || \
  echo "❌ Error al generar zip"
fi

echo ""
echo "Reinicia Cowork y Claude Code para que tomen los cambios."
