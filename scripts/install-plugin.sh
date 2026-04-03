#!/bin/bash

# --- Script Corregido para macOS ---

PLUGIN_NAME="email-triage"
GITHUB_REPO="novanoticia/email-triage-plugin"
VERSION_TAG="v3.1.0"

echo "🚀 Iniciando instalación automática del plugin '$PLUGIN_NAME' (versión: $VERSION_TAG)..."

# 1. Determinar la ruta base de datos del usuario de Claude/Cowork
user_name=$(whoami)
user_name_escaped=$(printf '%s\n' "$user_name" | sed 's/[[\.\*^$()+?{|]/\\&/g')
home_dir_escaped=$(printf '%s\n' "$HOME" | sed 's/[[\.\*^$()+?{|]/\\&/g')

# Buscar el proceso principal de Claude.app
claude_process=$(ps aux | grep "/Applications/Claude\.app/Contents/MacOS/Claude" | grep -v grep | head -n 1)

if [ -z "$claude_process" ]; then
    echo "⚠️ No se encontró ningún proceso activo de Claude."
    exit 1
fi

# 2. Instalar el plugin
echo "📦 Instalando el plugin '$PLUGIN_NAME'..."

# Ruta donde se instalan los plugins de Claude
PLUGIN_DIR="$HOME/Library/Application Support/Claude/Claude Extensions"

# Crear el directorio si no existe
mkdir -p "$PLUGIN_DIR"

# Eliminar el directorio existente si ya existe
if [ -d "$PLUGIN_DIR/$PLUGIN_NAME" ]; then
    echo "   Eliminando la instalación existente del plugin..."
    rm -rf "$PLUGIN_DIR/$PLUGIN_NAME"
fi

# Clonar el repositorio del plugin
echo "   Clonando el repositorio del plugin..."
git clone --depth 1 --branch "$VERSION_TAG" "https://github.com/$GITHUB_REPO.git" "$PLUGIN_DIR/$PLUGIN_NAME" 2>&1 | tee git_clone.log

# Verificar si la clonación fue exitosa
if [ $? -eq 0 ]; then
    echo "✅ Plugin '$PLUGIN_NAME' instalado correctamente en $PLUGIN_DIR/$PLUGIN_NAME"
    echo "🔍 Verificando la estructura del plugin..."
    ls -la "$PLUGIN_DIR/$PLUGIN_NAME"
else
    echo "❌ Error al instalar el plugin '$PLUGIN_NAME'"
    echo "   Revisa el archivo 'git_clone.log' para más detalles."
    exit 1
fi

echo "🎉 Instalación completada."

# Copiar archivos necesarios al directorio correcto
echo "📂 Copiando archivos necesarios..."
if [ -d "$PLUGIN_DIR/$PLUGIN_NAME/plugins/email-triage" ]; then
    cp -r "$PLUGIN_DIR/$PLUGIN_NAME/plugins/email-triage/." "$PLUGIN_DIR/$PLUGIN_NAME/"
    echo "✅ Archivos copiados correctamente."
else
    echo "❌ No se encontró el directorio 'plugins/email-triage' en el repositorio clonado."
    exit 1
fi

# Registrar el plugin (si es necesario)
if [ -f "$PLUGIN_DIR/$PLUGIN_NAME/fix-cowork-version.sh" ]; then
    echo "🔧 Registrando el plugin..."
    chmod +x "$PLUGIN_DIR/$PLUGIN_NAME/fix-cowork-version.sh"
    "$PLUGIN_DIR/$PLUGIN_NAME/fix-cowork-version.sh"
    if [ $? -eq 0 ]; then
        echo "✅ Plugin registrado correctamente."
    else
        echo "❌ Error al registrar el plugin."
        exit 1
    fi
else
    echo "ℹ️ No se encontró un script de registro para el plugin."
fi

# Verificar la estructura del plugin
echo "🔍 Verificando la estructura del plugin..."
if [ -d "$PLUGIN_DIR/$PLUGIN_NAME" ]; then
    echo "   Contenido del directorio del plugin:"
    ls -la "$PLUGIN_DIR/$PLUGIN_NAME"
    if [ -f "$PLUGIN_DIR/$PLUGIN_NAME/skills/email-triage/SKILL.md" ] && [ -f "$PLUGIN_DIR/$PLUGIN_NAME/skills/email-triage/config.yaml" ]; then
        echo "✅ Los archivos SKILL.md y config.yaml están presentes."
    else
        echo "❌ Faltan archivos necesarios en el directorio del plugin."
        exit 1
    fi
else
    echo "❌ El directorio del plugin no existe."
    exit 1
fi