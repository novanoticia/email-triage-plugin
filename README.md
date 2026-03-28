# Email Triage Plugin v2.0

Filtrado inteligente de correo electrónico para Claude Cowork y Claude Code.

## Qué hace

Evalúa correos electrónicos usando un criterio de **valor diferencial**:
no "¿es importante?" sino "¿leer esto cambiaría algo concreto para mí?"

Analiza tu bandeja de entrada y carpetas de lectura pendiente, puntúa
cada correo con un sistema ponderado y mueve los de alto valor a una
carpeta de prioridad.

## Novedades en v2.0

- **Lectura del cuerpo del email** — evalúa contenido real, no solo asuntos
- **Puntuación ponderada** — keywords con pesos configurables (alto/medio/bajo)
- **Calibración estadística** — extrae patrones reales del historial
- **Lotes de hasta 50 correos** — procesamiento más eficiente
- **Umbral configurable** — ajusta la selectividad según tu experiencia
- **Modo degradado** — si no puede leer el cuerpo, continúa con asunto/remitente

## Instalación

### Cowork (desktop)

1. Descarga o clona este repositorio
2. Comprime como ZIP: `zip -r email-triage.zip email-triage-plugin/`
3. En Cowork → Plugins → "+" → Upload → selecciona el ZIP
4. Edita `skills/email-triage/config.yaml` con tus datos

### Claude Code (CLI)

```bash
# Desde marketplace
claude plugin install email-triage@tu-marketplace

# Desde directorio local
claude plugin install ./email-triage-plugin
```

## Configuración

Edita `skills/email-triage/config.yaml` antes del primer uso:

### Campos básicos
- **usuario**: nombre, perfil profesional, proyectos activos
- **correo**: proveedor (icloud/gmail/otro), nombre de cuenta
- **carpetas**: bandeja, pendiente, destino, historial

### Modos de interacción
- **confirmacion**: pregunta uno a uno (recomendado al inicio)
- **lote**: presenta todos y pide confirmación global
- **silencioso**: mueve automáticamente (tras validar el criterio)

### Puntuación (nuevo en v2.0)
- **umbral_mover**: puntuación mínima para recomendar MOVER (default: 3)
- **leer_cuerpo**: activar/desactivar lectura del contenido del email
- **palabras_clave_boost**: con peso `alto` (+3), `medio` (+2) o `bajo` (+1)
- **palabras_clave_penalizar**: restan -2 por aparición

## Conectores necesarios

| Proveedor | Conector |
|-----------|----------|
| iCloud    | Control your Mac (osascript) |
| Gmail     | Gmail MCP |
| Otro      | Según disponibilidad |

## Estructura

```
email-triage-plugin/
├── .claude-plugin/
│   ├── marketplace.json    # Registro del marketplace
│   └── plugin.json         # Manifest del plugin
├── plugins/
│   └── email-triage/
│       ├── .claude-plugin/
│       │   └── plugin.json # Manifest con versión
│       ├── .mcp.json       # Configuración de conectores
│       └── skills/
│           └── email-triage/
│               ├── SKILL.md     # Lógica de triaje
│               └── config.yaml  # Perfil del usuario
├── LICENSE
└── README.md
```

## Créditos

Diseñado por Pablo Rodríguez López (mindandhealth.org) con asistencia de Claude.

## Licencia

Apache 2.0 — Uso libre, atribución apreciada.
