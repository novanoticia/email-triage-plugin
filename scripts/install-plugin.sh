#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# install-plugin.sh — email-triage-plugin
# Instalación / actualización automática para macOS
#
# Flujo:
#   1. Verifica dependencias (git, python3).
#   2. Protege ~/.email-triage/ y rescata la configuración antigua si procede.
#   3. Clona (o actualiza con fetch + reset) el marketplace en la
#      ruta correcta que Claude Code/Cowork esperan:
#        ~/.claude/plugins/marketplaces/email-triage-plugin/
#   4. Lee la versión dinámicamente desde plugin.json.
#   5. Ejecuta fix-cowork-version.sh para sincronizar el plugin
#      con la caché de Claude Code y con el rpm de Cowork.
#   6. Crea la configuración personal desde la plantilla si hace falta.
#   7. Imprime instrucciones claras de siguiente paso.
# ═══════════════════════════════════════════════════════════════

PLUGIN_NAME="email-triage"
GITHUB_REPO="novanoticia/email-triage-plugin"
BRANCH="main"
MARKETPLACE_DIR="$HOME/.claude/plugins/marketplaces/email-triage-plugin"
TELEMETRY_DIR="$HOME/.email-triage"
USER_CONFIG="$TELEMETRY_DIR/config.yaml"
REPO_CONFIG="plugins/$PLUGIN_NAME/skills/$PLUGIN_NAME/config.yaml"

# Flag opt-in (issue #4): --cowork reenvía a fix-cowork-version.sh el
# parcheo del rpm efímero de Cowork. Por defecto NO se toca el rpm: en
# Cowork la vía canónica es el marketplace; aquí solo se sincroniza la
# caché de Claude Code.
COWORK_FLAG=""
for arg in "$@"; do
  [ "$arg" = "--cowork" ] && COWORK_FLAG="--cowork"
done

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

# ── Preparar el estado privado antes de migrar o actualizar el repo ──
# Este instalador también se distribuye como un único archivo descargable.
preparar_config_personal() {
  python3 -I - "$TELEMETRY_DIR" "$@" <<'PYTHON'
import os
import secrets
import shutil
import stat
import subprocess
import sys


def existe_config(directorio):
    try:
        datos = os.stat("config.yaml", dir_fd=directorio, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(datos.st_mode) or datos.st_uid != os.geteuid():
        raise OSError("config.yaml debe ser un archivo regular de tu propiedad")
    return True


def preparar(ruta, origen=None):
    os.umask(0o077)
    try:
        os.mkdir(ruta, 0o700)
    except FileExistsError:
        pass

    # Fijar el directorio por descriptor mantiene las escrituras dentro
    # del mismo directorio que acabamos de comprobar.
    directorio = os.open(ruta, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(directorio).st_uid != os.geteuid():
            raise OSError("el directorio debe ser de tu propiedad")
        if sys.platform == "darwin":
            # Una ACL de macOS puede dar acceso pese a los permisos 0700.
            subprocess.run(
                ["/bin/chmod", "-N", f"/dev/fd/{directorio}"],
                pass_fds=(directorio,), check=True,
            )
        if stat.S_IMODE(os.fstat(directorio).st_mode) != 0o700:
            os.fchmod(directorio, 0o700)
        if stat.S_IMODE(os.fstat(directorio).st_mode) != 0o700:
            raise OSError("no se pudieron verificar los permisos 0700")
        if existe_config(directorio):
            return "existente"
        if origen is None:
            return "ausente"

        with open(origen, "rb") as entrada:
            temporal = f".config-{secrets.token_hex(8)}.tmp"
            salida = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                             0o600, dir_fd=directorio)
            try:
                with os.fdopen(salida, "wb") as copia:
                    shutil.copyfileobj(entrada, copia)
                # Publicar el archivo completo sin sustituir una configuración
                # que otra ejecución haya creado entretanto.
                try:
                    os.link(temporal, "config.yaml", src_dir_fd=directorio,
                            dst_dir_fd=directorio, follow_symlinks=False)
                except FileExistsError:
                    if existe_config(directorio):
                        return "existente"
                    raise
            finally:
                os.unlink(temporal, dir_fd=directorio)
        return "creado"
    finally:
        os.close(directorio)


try:
    print(preparar(*sys.argv[1:]))
except (OSError, subprocess.CalledProcessError) as error:
    sys.exit(f"❌ No se pudo preparar el estado privado en {sys.argv[1]}: {error}")
PYTHON
}

ESTADO_CONFIG=$(preparar_config_personal)
echo "🔒 Estado privado verificado: $TELEMETRY_DIR (permisos 700)"

# ── Clonar o actualizar el repo ───────────────────────────────
mkdir -p "$(dirname "$MARKETPLACE_DIR")"

if [ -d "$MARKETPLACE_DIR/.git" ]; then
  echo "📥 Repo existente detectado. Actualizando (fetch + reset a origin/$BRANCH)..."

  # ── 2-pre. Rescatar config personalizado (migración v3.3 → v3.4+) ──
  # En v3.3 el config del usuario vivía DENTRO del repo; el reset --hard
  # de abajo lo destruiría sin aviso. Si todavía no existe el config
  # personal de v3.4+ y el del repo difiere de su plantilla original
  # (HEAD local), rescatarlo ANTES de tocar nada.
  if [ "$ESTADO_CONFIG" = "ausente" ] && [ -f "$MARKETPLACE_DIR/$REPO_CONFIG" ]; then
    if git -C "$MARKETPLACE_DIR" diff HEAD --quiet -- "$REPO_CONFIG"; then
      :
    else
      if [ "$?" -ne 1 ]; then
        echo "❌ No se pudo comprobar si el config del repo está personalizado." >&2
        exit 1
      fi
      ESTADO_CONFIG=$(preparar_config_personal "$MARKETPLACE_DIR/$REPO_CONFIG")
      if [ "$ESTADO_CONFIG" = "creado" ]; then
        echo "🛟 Config personalizado detectado en el repo (formato v3.3)."
        echo "   Rescatado a: $USER_CONFIG"
      fi
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

# ── Leer versión dinámicamente desde plugin.json ──────────────
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

# ── Sincronizar caché de Claude Code (rpm de Cowork solo con --cowork) ──
FIX_SCRIPT="$MARKETPLACE_DIR/fix-cowork-version.sh"
if [ -f "$FIX_SCRIPT" ]; then
  echo ""
  echo "🔧 Sincronizando la caché de Claude Code..."
  [ -n "$COWORK_FLAG" ] && echo "   (--cowork: además se parcheará el rpm de Cowork)"
  chmod +x "$FIX_SCRIPT"
  if "$FIX_SCRIPT" $COWORK_FLAG; then
    echo "✅ Sincronización completada"
  else
    echo "⚠️  fix-cowork-version.sh devolvió errores (revísalos arriba)"
  fi
else
  echo "⚠️  fix-cowork-version.sh no encontrado — omitiendo sync"
fi

# ── Config personal persistente (desde v3.4) ──────────────────
# El config del usuario vive FUERA del repo para sobrevivir a
# `git reset --hard` en actualizaciones y no acabar en git.
ESTADO_CONFIG=$(preparar_config_personal "$MARKETPLACE_DIR/$REPO_CONFIG")
if [ "$ESTADO_CONFIG" = "existente" ]; then
  echo "🔒 Config personal preservado: $USER_CONFIG (no se ha tocado)"
else
  echo "📝 Creado config personal desde plantilla: $USER_CONFIG"
fi

# ── 5c. Verificación de integridad de la instalación (issue #12) ──
# La vía canónica del PASO 1 (references/mail-consolidado.applescript) da la
# sanitización determinista de un solo round-trip. Si falta, el SKILL degrada
# en SILENCIO al fallback manual S0–S5. Aquí avisamos si el árbol quedó
# incompleto — sin abortar: una instalación sana no añade ruido.
SKILL_DIR="$MARKETPLACE_DIR/plugins/$PLUGIN_NAME/skills/$PLUGIN_NAME"
ESPERADOS=(
  "SKILL.md"
  "config.yaml"
  "config-veloz.yaml"
  "scripts/triage_helpers.py"
  "references/mail-consolidado.applescript"
)
# CM2 (auditoría 2026-08-07): el resto de referencias NO se enumera a mano. La
# divulgación progresiva mueve pasos enteros a references/ (1.C hilos, 2
# calibración, 5.B telemetría…) y una lista escrita a mano se queda corta en
# silencio justo cuando más importa: un fichero ausente no rompe la ejecución,
# solo degrada el paso. Derivamos la lista de lo que el propio SKILL.md cita,
# que es la definición operativa de "referencia que hace falta".
if [ -f "$SKILL_DIR/SKILL.md" ]; then
  while IFS= read -r rel; do
    [ -n "$rel" ] && ESPERADOS+=("$rel")
  done < <(grep -oE 'references/[A-Za-z0-9._-]+\.(md|applescript)' \
             "$SKILL_DIR/SKILL.md" | sort -u)
fi
faltan=()
for rel in "${ESPERADOS[@]}"; do
  [ -f "$SKILL_DIR/$rel" ] || faltan+=("$rel")
done
if [ ${#faltan[@]} -gt 0 ]; then
  echo ""
  echo "⚠️  Instalación incompleta: faltan ${#faltan[@]} fichero(s) del skill."
  for rel in "${faltan[@]}"; do
    echo "     - $rel"
  done
  echo "   El plugin puede caer al fallback manual (S0–S5 por el modelo) en vez"
  echo "   de la vía canónica del PASO 1. Reinstala para restaurarlos:"
  echo "     bash scripts/install-plugin.sh"
else
  echo "🔎 Integridad del skill verificada (${#ESPERADOS[@]}/${#ESPERADOS[@]} ficheros)"
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
