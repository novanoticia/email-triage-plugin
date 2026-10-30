<!-- i18n:inicio -->
# OpenRouter Decisions opcional

Tercera opción externa junto a Jev y OpenAI Decisions. Usa el mismo núcleo
`scripts/clasificadores.py`, sanitización S0–S5, scoring y frenos. Desactivada
por defecto; retirar el archivo o poner `activo: false` conserva el principal.
No combinar con Jev, OpenAI Decisions ni el evaluador nativo en una sesión.
Con varias capas activas, preguntar cuál usar antes de enviar datos.

## Configuración

Copiar `config-openrouter.yaml` a la base de estado personal resuelta en el
PASO 0 (normalmente `~/.email-triage`), fuera del repo. Antes de activarla,
explicar el envío de asunto, remitente y extracto sanitizados (≤1500 caracteres),
perfil mínimo y preguntas a **OpenRouter y al proveedor que sirva el modelo**,
con facturación independiente. Sanitizar no anonimiza. No enviar cuerpos crudos,
adjuntos, historial, pesos, carpetas ni controles. No presuponer retención cero,
residencia europea ni las mismas condiciones de privacidad para distintos modelos.

La clave se crea en <https://openrouter.ai/settings/keys> y se inyecta como
`OPENROUTER_API_KEY` mediante el gestor de secretos del cliente. No pedirla en
el chat, guardarla en YAML/git, pasarla por argumentos ni imprimir el entorno.
Guía de Llavero y Terminal en macOS:
<https://github.com/novanoticia/email-triage-plugin/blob/main/docs/clave-openai-macos.md>
(no viaja con el plugin instalado: proporcionar la URL).
Las claves de OpenAI y TypeSafe no la sustituyen. Requiere Python con PyYAML y
HTTPS a `openrouter.ai`.

```yaml
activo: true
acepta_envio_datos: true
modo: comparar
modelo: microsoft/microsoft-decision-1
max_llamadas: 5
timeout_segundos: 15
confianza_minima: 0.8
tolerancia_dudas: 0
```

El nombre visible Microsoft-Decision-1 corresponde al ID completo
`microsoft/microsoft-decision-1`. Para cambiar de modelo, cambiar solo `modelo`
por el ID de otro **modelo compatible con Decisions y preguntas Choice**, por
ejemplo `typesafe/jev-1.14` o `openai/gpt-6-luna-decisions`. Esto no convierte
modelos de chat en modelos de decisión. El endpoint y la clave se mantienen.
El modelo devuelto debe coincidir con el solicitado o ser su snapshot con sufijo
`-YYYYMMDD`; otro modelo se rechaza. No se admiten selección automática ni URLs.
La sintaxis del ID se valida localmente; disponibilidad y soporte los valida la API.

Un campo `modelo` omitido usa el valor predeterminado; vacío se rechaza, sin
sustitución automática. Cambiar el modelo no modifica los umbrales.

## Confianza al cambiar de modelo

La validación comprueba estructura y coherencia numérica; no demuestra que las
probabilidades o la confianza estén calibradas igual entre modelos. El núcleo
aplica el menor valor entre la confianza declarada y la concentración calculada
como `(max(p)-1/n)/(1-1/n)`, con las guardas de redondeo existentes. Ese freno
conservador no convierte la confianza en probabilidad de acierto ni garantiza
resultados equivalentes a Jev.

Al cambiar de modelo, empezar en `comparar` con una muestra etiquetada por una
persona; comprobar cobertura, errores por tier, abstenciones y comportamiento de
los umbrales antes de activar híbrido. Revisar si los umbrales son adecuados;
no ajustarlos automáticamente ni relajar frenos para conseguir propuestas.

## Errores y ayuda del orquestador

`motivo` conserva el código original; `diagnostico_error` añade una categoría
segura. Explicar la causa y el siguiente paso en el idioma elegido, usando esta
tabla como orientación, sin reproducir mensajes HTTP ni credenciales:

| Diagnóstico | Explicación y siguiente paso |
|---|---|
| `credencial_local` | Clave ausente o inválida en el entorno; revisar su carga y el proceso que ejecuta el plugin. |
| `autenticacion` | HTTP 401: autenticación rechazada; comprobar o renovar la clave de OpenRouter. |
| `saldo_o_credito` | HTTP 402: revisar saldo, crédito y límites de gasto de la cuenta. |
| `acceso_denegado` | HTTP 403: revisar permisos y restricciones de la cuenta. |
| `peticion_o_modelo`, `recurso_o_modelo`, `peticion_o_capacidades` | HTTP 400/404/422: revisar ID, disponibilidad y soporte de Choice; el código solo no permite afirmar que el modelo no existe o es incompatible. |
| `limite_solicitudes` | HTTP 429: se alcanzó un límite de solicitudes; esperar o revisar límites antes de una nueva ejecución explícita. |
| `conexion_o_timeout` | Fallo de conexión o timeout; no se distinguen con el transporte compartido. Revisar conectividad y tiempo de espera; puede haber consumo. |
| `fallo_servicio` | HTTP 5xx: fallo del servicio; conservar el principal y comprobar el estado del proveedor. |
| `identificador_modelo_invalido` | ID vacío o con formato no admitido; indicar un ID completo de Decisions. |
| `modelo_distinto` | La respuesta identifica otro modelo; revisar el ID y su resolución a snapshot. |
| `respuesta_invalida_o_incompatible` | Respuesta incompleta o que incumple el contrato; conservar el principal y revisar compatibilidad. |
| `llamadas_suspendidas` | Un fallo previo detuvo las llamadas pendientes; explicar primero ese fallo. |

No interpretar un error como una clasificación ni añadir reintentos automáticos.

## Protocolo

Aplicar íntegramente el protocolo de `references/jev.md`, incluidos sanitización,
controles del principal, confianza, tolerancia a dudas, config canónico de la
base, simulación, revisión y autorización de movimientos. Sustituir:

- `scripts/jev.py` por `scripts/openrouter.py`.
- `config-jev.yaml` y `--config-jev` por `config-openrouter.yaml` y
  `--config-openrouter`.
- La clave por `OPENROUTER_API_KEY`.
- `proveedor` por `openrouter` y `evaluacion_jev` por `evaluacion_openrouter`.

`preparar` recibe datos por stdin y sanitiza sin red. `comparar --config
RUTA_CONFIG_PERSONAL --config-openrouter RUTA_CAPA` compara con el principal y
fuerza simulación durante toda la sesión, incluidos fallos. Acepta
`--config-veloz` y `--config-ensayo` en los mismos casos que Jev.
`evaluar` exige `modo: hibrido` elegido explícitamente: integrar solo veredictos
validados, con revisión obligatoria, `payload_scoring` en 4.D y PASO 5 habitual.
El adaptador nunca mueve ni concede permisos. Una simulación solicitada prevalece.
Config ilegible o inválido: detener delegación y conservar simulación.

## Contrato, consumo y pruebas

Contrato consultado el 2026-10-30:
<https://openrouter.ai/blog/insights/what-is-jev/> y
<https://openrouter.ai/microsoft/microsoft-decision-1>.
`POST https://openrouter.ai/api/alpha/decisions`, Bearer, JSON con `model`,
`state` y `questions`. Choice usa `criteria` y `instructions`; `answers` es un
objeto por criterio con `choice`, `probabilities` y `confidence`, como Jev.
Cobertura exacta y validación del núcleo común: probabilidades finitas,
suma válida, opción máxima y confianza conservadora. No inventar evidencias.
Una llamada por correo, máximo 1–50 por ejecución, timeout 1–60 s; sin reintentos
ni redirecciones en el cliente. OpenRouter administra su propio enrutamiento.

Se cuentan `usage.input_tokens` y `usage.output_tokens`. El coste se declara
**desconocido** tras enviar: no se extrapola la tarifa de Microsoft a otros
modelos ni se confunde una estimación con la factura de OpenRouter.

`python3 -m unittest tests.test_openrouter -v` usa transporte simulado y correos
ficticios, sin claves reales ni gasto. Verifica el mecanismo, no la precisión
ni una llamada real. Validar la calidad requiere una muestra revisada por una
persona, como Jev. Primera comprobación real: correos ficticios y sin movimientos.
<!-- i18n:fin -->
