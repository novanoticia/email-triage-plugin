# Email Triage Plugin

Filtrado inteligente de correo electrónico para Claude Cowork y Claude Code.

## Qué hace

Evalúa correos electrónicos usando un criterio de **valor diferencial**:
no "¿es importante?" sino "¿leer esto cambiaría algo concreto para mí?"

Analiza tu bandeja de entrada y carpetas de lectura pendiente, identifica
correos de alto valor y los mueve a una carpeta/etiqueta de prioridad,
siempre con tu confirmación previa.

## Instalación

### Cowork (desktop)

1. Descarga o clona este repositorio
2. Comprime la carpeta como ZIP: `zip -r email-triage.zip email-triage-plugin/`
3. En Cowork → Plugins → "+" → Upload → selecciona el ZIP
4. Edita `skills/email-triage/config.yaml` con tus datos

### Claude Code (CLI)

```bash
# Si lo tienes en un marketplace
claude plugin install email-triage@tu-marketplace

# O instalación directa desde directorio local
claude plugin install ./email-triage-plugin
```

## Configuración

Edita `skills/email-triage/config.yaml` antes del primer uso:

- **usuario**: nombre, perfil profesional, proyectos activos
- **correo**: proveedor (icloud/gmail/otro), nombre de cuenta
- **carpetas**: nombres de bandeja, carpeta pendiente, destino, historial
- **interaccion**: modo (confirmacion/lote/silencioso), límite por sesión

Ver `config.yaml` para ejemplos de perfiles de distintos roles profesionales.

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
│   └── plugin.json          # Manifest del plugin
├── .mcp.json                # Configuración de conectores
├── skills/
│   └── email-triage/
│       ├── SKILL.md          # Lógica de triaje
│       └── config.yaml       # Perfil del usuario
└── README.md                 # Este archivo
```

## Créditos

Diseñado por Pablo Rodríguez López (mindandhealth.org) con asistencia de Claude.

## Licencia

Apache 2.0 — Uso libre, atribución apreciada.
