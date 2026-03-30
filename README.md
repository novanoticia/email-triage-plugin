# Email Triage Plugin v3.0.1

Filtrado epistémico de correo electrónico para Claude Cowork y Claude Code.

## Qué hace

Evalúa correos electrónicos usando un marco de **racionalidad bayesiana**
inspirado en las [LessWrong Sequences](https://www.lesswrong.com/rationality):
no "¿es importante?" sino "¿leer esto cambiaría algo concreto para mí?"

Analiza cada correo con **30 criterios epistémicos**, genera una puntuación
multi-eje (valor decisional, calidad epistémica, riesgo de manipulación,
coste cognitivo, presión de acción) y clasifica en **4 tiers** con una
explicación legible de cada decisión.

## Filosofía

La mayoría de clasificadores de correo preguntan "¿es urgente?". Este plugin
pregunta algo distinto:

- **¿Cambia una decisión?** (Value of Information)
- **¿Actualiza mis predicciones?** (Bayesian Surprise)
- **¿La evidencia es genuina o filtrada?** (Filtered Evidence)
- **¿Explora o racionaliza?** (Forward vs Backward Flow)
- **¿Es urgencia real o teatro?** (Urgencia fabricada)
- **¿Está anclado a hechos verificables?** (Entangled Truths)

El resultado no es un simple "urgente/no urgente" sino un filtro de:
**valor decisional, calidad epistémica, coste cognitivo y riesgo de manipulación**.

## Novedades en v3.0

- **30 criterios epistémicos** — inspirados en LessWrong Sequences, organizados
  en 4 grupos: valor base, actualización bayesiana, diseño atencional, anti-sesgo
- **Scoring multi-eje** — 5 ejes independientes en lugar de una puntuación plana
- **4 tiers de routing** — `reply_needed`, `review`, `reading_later`, `archive`
  (en lugar del binario MOVER/DEJAR)
- **Explicación obligatoria** — top 3 razones positivas, top 3 negativas, rationale
  en español llano por cada correo
- **12 criterios core** — siempre evaluados; 18 adicionales activados por contexto
- **Hard rules expandidas** — pregunta directa (+4), deadline (+4), hilo blocker (+5),
  bulk sender (-4)
- **Telemetría** — registro de vectores, scores, explicaciones y correcciones
  del usuario para mejora continua
- **Compatible con v2.0** — mantiene acceso al cuerpo, calibración estadística,
  puntuación por keywords y lotes optimizados

## Los 5 ejes de scoring

| Eje | Rango | Qué mide |
|-----|-------|----------|
| **Valor decisional** | 0..10 | ¿Cambia una decisión, predicción o acción? |
| **Calidad epistémica** | -10..10 | ¿La evidencia es nueva, verificable, bien razonada? |
| **Riesgo de manipulación** | -10..0 | ¿El remitente optimiza para influir, no para informar? |
| **Coste cognitivo** | -5..0 | ¿Cuánto esfuerzo mental requiere procesarlo? |
| **Presión de acción** | 0..10 | ¿Requiere respuesta/acción con consecuencias reales? |

## Los 4 tiers

| Tier | Score | Significado |
|------|-------|-------------|
| `reply_needed` | ≥ 10 | Requiere respuesta o acción directa |
| `review` | 4–9 | Vale la pena leer con atención |
| `reading_later` | 0–3 | Interesante pero no urgente |
| `archive` | < 0 | Ruido, ritual o manipulación |

## Los 30 criterios epistémicos

### Grupo A — Valor base
1. **Cambia algo concreto** — ¿Leer esto cambiaría algo que vaya a hacer?

### Grupo B — Actualización bayesiana
2. **Cambio de predicciones** — ¿Altera mis predicciones?
3. **Sorpresa bayesiana** — ¿Qué tan inesperada es?
4. **Evidencia filtrada** — ¿Cuál es el algoritmo del remitente?
5. **Forward vs backward flow** — ¿Explora o racionaliza?

### Grupo C — Diseño atencional y utilidad
6. **Retorno atencional** — ¿Buena inversión de 2 minutos?
7. **Confusión productiva** — ¿Revela discrepancia importante?
8. **Impacto causal real** — ¿Cuánto cambia el resultado?
9. **Ruido social** — ¿Señal o ritual?
10. **Apertura de opciones** — ¿Abre opciones nuevas?
11. **Distancia inferencial** — ¿Cuánto cuesta entenderlo?
12. **Agente estratégico** — ¿Optimiza para verdad o influencia?
13. **Densidad informativa** — ¿Cuánta info nueva por línea?
14. **Urgencia real vs fabricada** — ¿Consecuencias o solo tono?
15. **Relevancia longitudinal** — ¿Mi yo futuro lo agradecerá?

### Grupo D — Anti-sesgo y calidad argumentativa
16. **Motivated stopping** — ¿Cierre prematuro?
17. **Motivated continuation** — ¿Decisión artificialmente prolongada?
18. **True rejection** — ¿Objeción real o excusa?
19. **Third alternative** — ¿Falsa dicotomía?
20. **Privileging the hypothesis** — ¿Hipótesis sin evidencia?
21. **Proper humility** — ¿Duda operativa o paralizante?
22. **Positive bias** — ¿Solo casos a favor?
23. **Argument screens off authority** — ¿Evidencia o cargo?
24. **Hug the query** — ¿Pegado a la decisión real?
25. **Semantic stopsigns** — ¿Jerga que cierra investigación?
26. **Fake justification** — ¿Conclusión anterior al razonamiento?
27. **Fake optimization criteria** — ¿Criterio oportunista?
28. **Entangled truths** — ¿Anclado a hechos verificables?
29. **Cached thought** — ¿Original o plantilla?
30. **Absence of expected evidence** — ¿Falta algo que debería estar?

## Instalación

### Cowork (desktop) — recomendado

Instala el ZIP para que el plugin persista entre reinicios:

1. Descarga **[email-triage-v3.0.1.zip](https://github.com/novanoticia/email-triage-plugin/releases/latest)** desde Releases
2. En Cowork → Plugins → "+" → Upload → selecciona el ZIP
3. Edita `skills/email-triage/config.yaml` con tus datos

> **¿Por qué ZIP y no URL de GitHub?** Los plugins instalados como ZIP quedan
> registrados en "My Uploads" y persisten entre reinicios. Los instalados desde
> URL de GitHub pueden desaparecer al reiniciar Cowork.

### Claude Code (CLI)

```bash
# Desde marketplace
claude plugin install email-triage@email-triage-plugin

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

### Tiers y umbrales (v3.0)
- **tiers**: umbrales configurables para cada tier
- **hard_rules**: puntos fijos por señales deterministas

### Criterios epistémicos (v3.0)
- **criterios_epistemicos**: 30 criterios con pesos ajustables
- Cada criterio se puede activar/desactivar con `activo: true/false`
- 12 marcados como `core: true` se evalúan siempre

### Explicación y telemetría (v3.0)
- **explicacion**: cuántas razones positivas/negativas mostrar
- **telemetria**: qué registrar (vector, score, explicación, correcciones)

### Filtros (heredados de v2.0)
- **palabras_clave_boost**: con peso `alto` (+3), `medio` (+2) o `bajo` (+1)
- **palabras_clave_penalizar**: restan -2 por aparición
- **remitentes_prioritarios / ignorar**: hard rules de +3 / -99

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
│   └── plugin.json         # Manifest del plugin (v3.0.1)
├── plugins/
│   └── email-triage/
│       ├── .claude-plugin/
│       │   └── plugin.json # Manifest con versión
│       ├── .mcp.json       # Configuración de conectores
│       └── skills/
│           └── email-triage/
│               ├── SKILL.md     # Lógica de triaje epistémico
│               └── config.yaml  # Perfil + criterios + telemetría
├── LICENSE
└── README.md
```

## Troubleshooting

### "Mail.app no responde" o timeout en osascript

Mail.app debe estar abierto para que el skill acceda al correo. Si está
abierto y sigue fallando, comprueba en **Ajustes del Sistema → Privacidad
y Seguridad → Automatización** que Claude/Cowork tenga permiso para
controlar Mail.app. El skill reintentará hasta 3 veces con backoff
antes de informar del error.

### "No puedo acceder a Gmail" o conector no disponible

Verifica que el conector Gmail MCP esté activo en **Configuración → Conectores**
de Cowork. Si el token ha expirado, desconéctalo y vuelve a conectar.

### Carpeta no encontrada

Los nombres de carpeta en `config.yaml` deben coincidir exactamente con los
de tu cliente de correo (incluyendo mayúsculas). Si no estás seguro, el
skill listará las carpetas disponibles y te pedirá que elijas.

### El triaje parece impreciso

Asegúrate de que `usuario.perfil` en `config.yaml` describe bien tu rol
e intereses (mínimo 2-3 líneas). Sin perfil, el criterio "¿cambiaría algo
concreto para ti?" no tiene ancla y los resultados serán genéricos. También
puedes ajustar los pesos de los criterios epistémicos en la sección
`criterios_epistemicos` del config.

### Correos muy largos causan lentitud

Reduce `puntuacion.max_caracteres_cuerpo` a 300 o desactiva `leer_cuerpo`
si prefieres velocidad sobre precisión. El skill también procesa en sublotes
automáticamente cuando hay muchos correos con cuerpo.

## Novedades en v3.0.1

- **Manejo de errores explícito** — errores de conexión, permisos y timeouts
  informados al usuario con acciones sugeridas
- **Retry con backoff** — hasta 3 reintentos para operaciones de lectura,
  con esperas de 2s y 5s entre intentos
- **Protección contra emails enormes** — límites configurables de caracteres
  y líneas, procesamiento en sublotes
- **Modo degradado** — si no se puede leer el cuerpo, continúa con metadatos
  y advierte al usuario
- **Validación de config.yaml** — campos obligatorios marcados, setup guiado
  si faltan datos críticos
- **Metadata mejorada** — keywords, licencia y repositorio en plugin.json

## Historial de versiones

| Versión | Cambio principal |
|---------|-----------------|
| v3.0.1 | Resiliencia: manejo de errores, retry/backoff, modo degradado, validación de config, protección contra emails enormes |
| v3.0.0 | Scoring epistémico multi-eje, 30 criterios LessWrong, 4 tiers, explicaciones, telemetría |
| v2.0.0 | Puntuación ponderada, acceso al cuerpo, calibración estadística, lotes |
| v1.0.0 | Triaje básico con criterio de valor diferencial |

## Créditos

Diseñado por Pablo Rodríguez López ([mindandhealth.org](https://mindandhealth.org))
con asistencia de Claude.

Criterios epistémicos basados en las [Sequences](https://www.lesswrong.com/rationality)
de Eliezer Yudkowsky (LessWrong).

## Licencia

Apache 2.0 — ver [LICENSE](LICENSE).
