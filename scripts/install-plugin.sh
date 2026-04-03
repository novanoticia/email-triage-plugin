#!/bin/bash

# --- Script Autónomo para macOS ---
PLUGIN_NAME="email-triage"
GITHUB_REPO="novanoticia/email-triage-plugin"
VERSION_TAG="v3.1.0"

echo "🚀 Iniciando instalación autónoma del plugin '$PLUGIN_NAME' (versión: $VERSION_TAG)..."

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

# Crear el directorio del plugin
mkdir -p "$PLUGIN_DIR/$PLUGIN_NAME"

# Crear los archivos necesarios directamente en el script
echo "📂 Creando archivos necesarios..."
mkdir -p "$PLUGIN_DIR/$PLUGIN_NAME/skills/email-triage"

# Contenido de SKILL.md
cat <<  'EOF' > "$PLUGIN_DIR/$PLUGIN_NAME/skills/email-triage/SKILL.md"
# Email Triage Plugin

Este plugin permite triar correos electrónicos utilizando criterios epistémicos.

## Configuración

Edita el archivo `config.yaml` para personalizar el comportamiento del plugin.

## Uso

1. Abre Claude Code o Cowork.
2. Ejecuta el comando `/email-triage` para triar tus correos electrónicos.
EOF

# Contenido de config.yaml
cat <<  'EOF' > "$PLUGIN_DIR/$PLUGIN_NAME/skills/email-triage/config.yaml"
# Configuración del plugin Email Triage

# Campos básicos
usuario:
  nombre: "Tu Nombre"
  perfil: "Desarrollador de software"
  proyectos: ["Proyecto 1", "Proyecto 2"]

correo:
  proveedor: "gmail"
  nombre_cuenta: "tu.cuenta@gmail.com"

carpetas:
  bandeja: "INBOX"
  pendiente: "Pendiente"
  destino: "Archivado"
  historial: "Historial"

# Modos de interacción
modo: "confirmacion"

# Tiers y umbrales
tiers:
  reply_needed: 10
  review: 4
  reading_later: 0
  archive: -1

# Criterios epistémicos
criterios_epistemicos:
  - nombre: "Cambia algo concreto"
    peso: 5
    activo: true
    core: true
EOF

echo "✅ Archivos creados correctamente."

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
SKILLS_DIR="$PLUGIN_DIR/$PLUGIN_NAME/skills/email-triage"
if [ -d "$PLUGIN_DIR/$PLUGIN_NAME" ]; then
    echo "   Contenido del directorio del plugin:"
    ls -la "$PLUGIN_DIR/$PLUGIN_NAME"
    if [ -d "$SKILLS_DIR" ]; then
        echo "   Directorio skills/email-triage encontrado."
        echo "   Verificando archivos en: $SKILLS_DIR/"
        ls -la "$SKILLS_DIR/"
        if [ -f "$SKILLS_DIR/SKILL.md" ] && [ -f "$SKILLS_DIR/config.yaml" ]; then
            echo "✅ Los archivos SKILL.md y config.yaml están presentes."
        else
            echo "❌ Faltan archivos necesarios en el directorio del plugin."
            echo "   Archivos esperados: SKILL.md y config.yaml"
            exit 1
        fi
    else
        echo "❌ El directorio skills/email-triage no existe."
        echo "   Ruta esperada: $SKILLS_DIR/"
        exit 1
    fi
else
    echo "❌ El directorio del plugin no existe."
    exit 1
fi

echo "🎉 Instalación completada."