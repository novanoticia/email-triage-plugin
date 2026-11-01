<!-- i18n:inicio -->
# Modelos de decisión locales (Ollama) opcional

Cuarta opción de decisión junto a Jev, OpenAI Decisions y OpenRouter, y la única
en la que **el correo no sale del Mac**: el adaptador solo habla con `ollama
serve` en `http://127.0.0.1:11434/v1/systemone`, sin clave y sin el proxy del
entorno. Usa el mismo núcleo `scripts/clasificadores.py`, sanitización S0–S5,
scoring y frenos. Desactivada por defecto; retirar el archivo o poner
`activo: false` conserva el principal. No combinar con otra capa de evaluación
en una sesión; con varias activas, preguntar cuál usar antes de enviar datos.

## Lo que dicen las mediciones (léelo antes de activarla)

Sonda con 12 correos ficticios en un Mac de 16 GB (2026-11-01,
`scripts/sonda_decision_local.py`): **ninguna fila pasa el freno de `hibrido`**
(0 inciertos y confianza de al menos 0,8 en los 30 criterios), ni con las
preguntas tal cual, ni sin `__incierto__`, ni en inglés. `d1` responde en 3-4 s
con confianza mediana 0,46; `tev1:4b`, en 12-16 s con 0,11. Sirve para
`comparar` en local, sin coste y sin enviar nada fuera. En `hibrido` cada fila
vuelve al principal (`confianza_baja`), como debe: **no relajar el freno ni
`confianza_minima` para conseguir propuestas**.

## Configuración

Copiar `config-decision-local.yaml` a la base de estado personal resuelta en el
PASO 0 (normalmente `~/.email-triage`), fuera del repo. Antes de activarla,
explicar que el extracto sanitizado, el perfil mínimo y las preguntas van a un
servidor que corre en el propio Mac. El doble consentimiento se exige igual: el
plugin no puede saber qué escucha en ese puerto.

```yaml
activo: true
acepta_envio_datos: true
modo: comparar
modelo: d1:latest   # o tev1:4b; solo los dos sondeados
max_llamadas: 5
timeout_segundos: 60
confianza_minima: 0.8
tolerancia_dudas: 0
```

Requisitos en el Mac: Ollama instalado, el modelo descargado (`ollama pull d1`
o `ollama pull tev1:4b`) y el servidor abierto con contexto ampliado
(`OLLAMA_CONTEXT_LENGTH=16384 ollama serve`): la petición ocupa 6.700-9.300
tokens y con los 4.096 por defecto se recortaría. Guía de instalación (no viaja
con el plugin instalado: proporcionar la URL):
<https://github.com/novanoticia/email-triage-plugin/blob/main/docs/modelos-locales-macos.md>.

Solo se admiten `d1:latest` y `tev1:4b`: otro valor se rechaza con
`modelo_no_verificado`. El modelo devuelto debe ser exactamente el pedido
(`modelo_inesperado`).

## Errores frecuentes

| Motivo | Explicación y siguiente paso |
|---|---|
| `fallo_red_o_timeout` | `ollama serve` no está abierto o no respondió a tiempo; abrirlo y repetir. |
| `http_404` u otro `http_` | Probablemente el modelo no está descargado (no comprobado): `ollama list` y, si falta, `ollama pull d1`. |
| `modelo_no_verificado` | `modelo` distinto de `d1:latest` o `tev1:4b`. |
| `modelo_inesperado` | Ollama respondió con otro modelo. |
| `confianza_baja` | Lo esperado en `hibrido` con estos modelos: la fila vuelve al principal. |

No interpretar un error como una clasificación ni añadir reintentos automáticos.

## Protocolo

Aplicar íntegramente el protocolo de `references/jev.md`, incluidos
sanitización, controles del principal, confianza, tolerancia a dudas, config
canónico de la base, simulación, revisión y autorización de movimientos.
Sustituir:

- `scripts/jev.py` por `scripts/decision_local.py`.
- `config-jev.yaml` y `--config-jev` por `config-decision-local.yaml` y
  `--config-decision-local`.
- La clave: no hay ninguna; no pedirla ni buscarla.
- `proveedor` por `ollama_decision` y `evaluacion_jev` por
  `evaluacion_decision_local`.

`preparar` recibe datos por stdin y sanitiza sin red. `comparar --config
RUTA_CONFIG_PERSONAL --config-decision-local RUTA_CAPA` compara con el principal
y fuerza simulación. `evaluar` exige `modo: hibrido` elegido explícitamente.
El adaptador nunca mueve ni concede permisos. Una simulación solicitada
prevalece. Config ilegible o inválido: detener delegación y conservar simulación.

## Contrato y pruebas

Comprobado en un Mac real el 2026-11-01 (Ollama 0.40.13, `scripts/sonda_ollama.py`
y `scripts/sonda_decision_local.py`): `POST /v1/systemone` con `model`, `state`
y `questions` Choice (`criteria`, `instructions`), sin clave; `answers` por
criterio con `choice`, `probabilities` y `confidence`, `model` igual al pedido y
`usage` (`input_tokens`, `output_tokens: 0`). Mismo contrato que Jev. Sin coste.
Una llamada por correo, 1–50 por ejecución, timeout 1–60 s, sin reintentos ni
redirecciones.

`python3 -m unittest tests.test_decision_local -v` usa transporte simulado y un
servidor en `127.0.0.1`, sin Ollama ni red. Verifica el mecanismo, no la
calidad.
<!-- i18n:fin -->
