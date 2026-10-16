<!-- i18n:inicio -->
# Jev opcional: comparación externa, sin movimientos

Esta capa es independiente de `config-modelos.yaml`. No sustituye automáticamente
una delegación nativa ni se activa por mencionar un modelo económico. Su ausencia
o `activo: false` conserva el flujo habitual. Si se solicita comparar con Jev o
se encuentra la capa activa, **fuerza simulación antes de cualquier fase**, incluso
si después faltan permisos, clave, red o configuración. Nunca continuar esa sesión
con movimientos, aprendizaje, registro de propuestas o tareas programadas reales.
No combinar en la misma comparación Jev y el evaluador nativo.

## Activación y credenciales

Usa la base de estado resuelta por el PASO 0 (normalmente `~/.email-triage`). Copia
allí la plantilla `config-jev.yaml`, fuera del repositorio, solo cuando el usuario
quiera activarlo. Requiere ambos `activo: true` y `acepta_envio_datos: true`.
Antes de activarlos, explica qué se enviará y que hay facturación independiente.
Un archivo inválido desactiva la comparación; no corregirlo activando permisos.

La clave se obtiene en <https://console.typesafe.ai> y se inyecta en el entorno del
proceso como `TYPESAFE_API_KEY` mediante el gestor de secretos del cliente. No
pedir pegarla en el chat, guardarla en YAML/git, pasarla por argumentos, imprimirla
ni registrar el entorno. No usar credenciales de Claude/OpenAI para esta API.
El host necesita ejecutar Python con PyYAML y permitir HTTPS a `api.typesafe.ai`.
Si no puede, informa de la limitación y conserva el principal en simulación; no
simular una llamada real mediante otro modelo.

La configuración solo admite comparación, modelos fijados `jev-1.13.0` (estable, por defecto)
o `jev-1.14.0` (preview en la fecha de revisión), máximo de llamadas por ejecución 1–20 (defecto 5), timeout 1–60 s
(defecto 15) y confianza mínima 0–1 (defecto 0,8). No admite endpoints alternativos.
Desactivar o retirar el archivo revierte la integración sin cambiar el scoring.

## Protocolo del orquestador

1. Mantén las reglas habituales de lectura, sanitización S0–S5 y controles del
   principal. Selecciona un lote pequeño, preferentemente ficticio primero.
   No leer más mensajes para consumir el presupuesto. No enviar adjuntos ni hilos
   completos. Para esta comparación ambos evaluadores reciben el mismo extracto
   de máximo 1500 caracteres y el mismo perfil mínimo, sin conversación heredada.
2. `python3 scripts/jev.py preparar` recibe JSON por stdin con `perfil_minimo`
   (texto relevante de máximo 2000 caracteres) y `emails`. Cada correo tiene
   exclusivamente `id` ordinal local (`"1"`, no UID real), `asunto`, `remitente`,
   `cuerpo`. Entrega los datos al proceso sin interpolarlos en comandos. Este
   paso es local y sanitiza antes de exponer el contenido al modelo. El cuerpo
   crudo no se incluye en el prompt ni en archivos nuevos persistentes.
3. El principal evalúa `estado` devuelto por preparar y añade a cada fila
   `principal: {verdicts: {...}, no_aplica: {...}}` con cobertura exacta de los
   criterios activos; `no_aplica` mapea criterios condicionales a motivos. Añade
   `control` con los valores habituales calculados por el principal:
   `hard_rules`, `extra_points`, `forzar_reply_needed`, `tier_maximo`,
   `remitente_en_historial` y opcional `remitente_conteo_historial`. Conserva S0,
   ajuste y cap conforme al flujo actual; no delegues estos controles a Jev.
   Conserva `estado`, `huella`, `s0` e `id` intactos. La huella detecta cambios
   accidentales, no autentica al orquestador. No inventar una evaluación principal.
4. Pasa el documento enriquecido por stdin a
   `python3 scripts/jev.py comparar --config RUTA_CONFIG_PERSONAL --config-jev RUTA_CAPA`.
   Para veloz añade `--config-veloz RUTA_CONFIG_VELOZ`; usa la misma configuración
   efectiva en la evaluación principal. Resuelve las rutas por el PASO 0, nunca
   reemplaces el config personal por la plantilla para obtener un resultado.
5. La respuesta siempre indica `usar_principal: true` y
   `permitir_movimientos: false`, también ante fallos. No interpretar `ok: true`
   como autorización operativa. Una propuesta válida sirve solo para comparar.
   Con error de configuración, acceso, esquema, confianza baja o abstención,
   conserva la evaluación principal. Un bloqueo S0/cap no sale a la red.
6. Presenta al usuario, en su idioma, discrepancias de puntuación/tier, exclusiones,
   llamadas, duración HTTP y consumo observado. El principal es referencia, no
   verdad etiquetada. Jev no devuelve evidencias narrativas: no inventarlas.
   `evaluacion_jev` conserva veredictos, abstenciones y probabilidades validadas,
   incluso con baja confianza; no convierte esos casos en propuestas utilizables.
   `cobertura` muestra el total del lote y cuántas propuestas se compararon. No
   interpretar el acuerdo del subconjunto aceptado como precisión del lote completo.
   No afirmar ahorro, precisión o latencia global medidos sin datos equivalentes:
   aquí se ejecutan ambos evaluadores y la comparación añade coste.

Los temporales sanitizados usan directorio 700 y archivo 600 y se eliminan al
terminar, incluso si hay errores. No guardar propuestas en telemetría o aprendizaje.
El script no escribe archivos ni tiene herramientas del buzón. Una ausencia de
PyYAML impide esta comparación: el modo mental no puede sustituir la validación.

## Contrato y validación

Verificado en documentación oficial el **16 de octubre de 2026**:
<https://docs.typesafe.ai/api>, <https://docs.typesafe.ai/models>,
<https://docs.typesafe.ai/confidence> y
<https://docs.typesafe.ai/introduction/quickstart>.

`POST https://api.typesafe.ai/v1/systemone`, Bearer en Authorization, JSON con
`model`, `state`, `questions`. Cada criterio activo se convierte en una pregunta
Choice con sus opciones originales, `__incierto__` y, solo en los condicionales,
`__no_aplica__`. La pregunta real va en `instructions`: el identificador no se
interpreta como pregunta. No se envían pesos, carpetas, controles ni historial.
Las respuestas deben cubrir exactamente las preguntas y opciones, identificar el
modelo solicitado, contener probabilidades finitas que sumen uno y elegir una
opción máxima. Se exige confianza finita en [0,1] y se calcula además la fórmula publicada
`(max(p)-1/n)/(1-1/n)`. Como algunos ejemplos oficiales difieren numéricamente,
se conserva la confianza declarada y se usa el menor de ambos valores para el
umbral, señalando discrepancias; nunca se aumenta confianza. Esta medida no es
probabilidad de acertar. El umbral inicial es experimental.

Los veredictos válidos pasan por el mismo `cmd_scoring_dispatch`, con los mismos
pesos, reglas y controles del principal; no se acepta un score proporcionado por
Jev. Se rechazan JSON duplicados/no finitos, respuestas excesivas y redirecciones.
No hay reintentos: errores HTTP/red detienen las llamadas restantes. Los límites
son por invocación, no un presupuesto mensual ni global entre procesos.

## Costes y privacidad

Tarifa publicada para ambos modelos fijados: **0,042 USD por millón de tokens de
entrada; salida gratuita** (fecha anterior; comprobar cambios en /models).
100 000 tokens de entrada serían 0,0042 USD, aparte del coste del principal.
El consumo procede de `usage`; un timeout/error puede haber consumido tokens.
`coste_total_desconocido` lo señala: la estimación observada no sustituye la factura.

Activar esta capa envía a **TypeSafe AI, otro proveedor**, asunto, remitente y
extracto sanitizados, perfil mínimo y preguntas de evaluación. Sanitizar reduce
HTML, citas e instrucciones maliciosas; **no anonimiza datos personales**. Revisa
el perfil mínimo y los mensajes que eliges compartir. La clave solo se transmite
en la cabecera de autenticación, nunca en `state`.

Según <https://typesafe.ai/legal/privacy-policy>, los inputs no se usan para
entrenar o ajustar modelos; el procesamiento incluye infraestructura en EE. UU.
y proveedores de servicio, y la retención depende de las necesidades del servicio.
No asumir retención cero: <https://typesafe.ai/enterprise> la ofrece bajo condiciones
empresariales. El plugin no cambia los ajustes de privacidad de Claude/OpenAI;
introduce un destinatario y condiciones adicionales al habilitar esta opción.

## Pruebas y alcance inicial

`python3 -m unittest tests.test_jev -v` usa mensajes de una asociación ficticia,
direcciones `example.invalid` y transporte simulado: no requiere claves ni gasta
crédito. Verifica el mecanismo, no la precisión ni compatibilidad real de la API.
La primera comprobación real necesita una clave propia y consentimiento explícito;
pedir «compara Jev con el principal usando correos ficticios, sin movimientos».
La revisión con la skill oficial contrastó Choice, state, confianza y el cookbook
[Classification using confidence](https://docs.typesafe.ai/cookbooks/classification_using_confidence).
Se usa Choice incluso para opciones binarias/ordinales para conservar los
veredictos discretos del scoring existente y permitir abstención explícita;
convertirlos a Noul o Score exigiría calibrar una traducción nueva a esos veredictos.
Todas las preguntas de un correo se envían juntas y son independientes.

Antes de ampliar el modo, revisar una muestra etiquetada por una persona que
incluya consultas, spam, contexto insuficiente y correos que necesitan respuesta,
en los idiomas reales del usuario. Medir cobertura, errores por tier, coste y
latencia de extremo a extremo; comparar también los casos abstinentes. El tiempo
HTTP informado no mide el flujo completo ni el ahorro frente al principal.
No activar sustitución operativa a partir de estos tests. Una revisión humana de
las discrepancias precede a cualquier futura ampliación de modos.
<!-- i18n:fin -->
