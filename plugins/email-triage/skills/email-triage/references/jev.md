<!-- i18n:inicio -->
# Jev opcional: comparación y triaje híbrido

Esta capa es independiente de `config-modelos.yaml`. No sustituye automáticamente
una delegación nativa ni se activa por mencionar un modelo económico. Su ausencia
o `activo: false` conserva el flujo habitual. `comparar` (por defecto) fuerza
simulación durante toda la sesión, incluso con errores. `hibrido`, elegido
explícitamente por el usuario, permite integrar veredictos validados en el flujo
real descrito abajo. Una petición de simulación siempre prevalece sobre híbrido.
Si el modo no se puede determinar por un archivo ilegible/inválido, detener la
delegación y mantener simulación; nunca deducir autorización de movimiento.
No combinar Jev y el evaluador nativo en la misma sesión.

## Activación y credenciales

Usa la base de estado resuelta por el PASO 0 (normalmente `~/.email-triage`). Copia
allí la plantilla `config-jev.yaml`, fuera del repositorio, solo cuando el usuario
quiera activarlo. Requiere ambos `activo: true` y `acepta_envio_datos: true`.
Antes de activarlos, explica qué se enviará y que hay facturación independiente.
Un archivo inválido desactiva la delegación; no corregirlo activando permisos.

La clave se obtiene en <https://console.typesafe.ai> y se inyecta en el entorno del
proceso como `TYPESAFE_API_KEY` mediante el gestor de secretos del cliente. No
pedir pegarla en el chat, guardarla en YAML/git, pasarla por argumentos, imprimirla
ni registrar el entorno. No usar credenciales de Claude/OpenAI para esta API.
El host necesita ejecutar Python con PyYAML y permitir HTTPS a `api.typesafe.ai`.
Si no puede, informa de la limitación y conserva el principal en el modo de sesión; no
simular una llamada real mediante otro modelo.

La configuración admite `modo: comparar` (defecto) o `modo: hibrido`, el alias `jev-latest` (estable, por defecto),
`jev-preview` (opcional) o una versión fijada `jev-X.Y.Z`, máximo de llamadas por ejecución 1–20 (defecto 5), timeout 1–60 s
(defecto 15) y confianza mínima 0–1 (defecto 0,8). No admite endpoints alternativos.
Desactivar o retirar el archivo revierte la integración sin cambiar el scoring.

El servicio resuelve el alias en cada petición. El informe identifica
`modelo_solicitado` y `modelo_efectivo` por correo, también si cambia dentro del lote.
No se acepta un alias como versión efectiva; las versiones fijadas deben coincidir
exactamente. El formato de un ID no garantiza su disponibilidad: si TypeSafe lo
rechaza se conserva el principal. Las respuestas se validan también con versiones
nuevas. Un alias puede cambiar resultados sin actualizar el plugin; para reproducir
una comparación, fija la versión efectiva. No se modifica la configuración personal
existente: para adoptar el alias cambia su campo a `modelo: jev-latest` o elimínalo.

## Comparación: protocolo del orquestador

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
   criterios activos; `no_aplica` mapea criterios a motivos (desde v3.22.1, si
   incluye un criterio core, ese correo queda fuera de la comparación con
   `principal_no_comparable` y no sale a la red; el resto del lote sigue). Añade
   `control` con los valores habituales calculados por el principal:
   `hard_rules`, `extra_points`, `forzar_reply_needed`, `tier_maximo`,
   `remitente_en_historial` y opcionales `remitente_conteo_historial`,
   `prioritario` (el de `coincidencias`) y `remitente`. Conserva S0,
   ajuste y cap conforme al flujo actual; no delegues estos controles a Jev.
   Conserva `estado`, `huella`, `s0` e `id` intactos. La huella detecta cambios
   accidentales, no autentica al orquestador. No inventar una evaluación principal.
4. Pasa el documento enriquecido por stdin a
   `python3 scripts/jev.py comparar --config RUTA_CONFIG_PERSONAL --config-jev RUTA_CAPA`.
   Para veloz añade `--config-veloz RUTA_CONFIG_VELOZ`, y con el ensayo P3
   `--config-ensayo RUTA` (v3.21.31); usa la misma configuración
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

## Triaje real: modo híbrido explícito

Para utilizar Jev en el triaje real, copia la plantilla a la base personal y fija:

```yaml
activo: true
acepta_envio_datos: true
modo: hibrido
modelo: jev-latest
```

También puedes pedir «usa Jev en modo híbrido para este triaje»; aplica esos ajustes
solo en memoria y confirma el consentimiento de envío si no está ya autorizado.
No modifica automáticamente la configuración personal ni activa rutina.
El modo inicial sigue siendo comparación. Recomienda probar primero correos
ficticios; no presentes las pruebas simuladas como validación del modelo real.

1. El principal conserva PASO 0, 0.B, lectura, contexto de hilos/Enviados, S0–S5,
   calibración, hard rules, ajustes y señal de respuesta (4.A/4.C). Guarda localmente
   el mapa de ordinal a message-id. No reduzcas estas comprobaciones para ahorrar.
2. Usa `preparar` como en comparación. Su salida es solo preparación local, no
   selección de modo ni autorización. Añade a cada correo `control` y
   `contexto_suficiente` (booleano), **sin `principal`**. No hay que evaluar todos
   los criterios por duplicado ni fabricar una referencia. El principal solo marca
   contexto suficiente si ese extracto y perfil permiten juzgar los criterios;
   hilos ambiguos, antecedentes necesarios ausentes o recortes que pierden una
   instrucción relevante deben volver al principal. Si preparar no representa
   fielmente lo leído, no delegues. S0 y caps tampoco salen a la red.
3. Ejecuta `python3 scripts/jev.py evaluar --config RUTA_CONFIG_PERSONAL
   --config-jev RUTA_CAPA`, con el documento por stdin. `--config-veloz` aplica
   únicamente si el usuario pidió también veloz, y `--config-ensayo RUTA` si el
   scoring la lleva (v3.21.31). `evaluar` requiere configuración
   híbrida explícita; `comparar` nunca se convierte en ejecución real.
4. Por correo, `usar_principal: true` obliga a completar la evaluación en el
   principal antes de continuar; no significa que exista ya una evaluación de
   respaldo. Cualquier fallo global exige reevaluar todo el lote. Los límites de
   llamadas, errores, abstención y baja confianza conservan esta ruta. También
   reevalúa `ARCHIVE`, `REPLY_NEEDED`, distancia ≤1 a un umbral y discrepancias
   entre confianza declarada y calculada.
5. Con `usar_principal: false`, el principal **revisa siempre** los veredictos
   y `no_aplica` contra el extracto/perfil y los controles, conforme a
   `revision_obligatoria: true`. Jev no suministra evidencias narrativas:
   la explicación se redacta a partir del correo, sin atribuírsela a Jev ni
   inventarla. Si encuentra contradicciones, falta de contexto o una omisión
   injustificada, reevalúa en el principal. No basta con confiar en la probabilidad.
6. Tras esa revisión, usa `payload_scoring` y `propuesta` en 4.D con el scoring
   determinista existente. No cambia `scoring.modo` persistente. Las filas que
   vuelven al principal siguen su evaluación normal. No sumar dos veces ajustes.
   El flag global `usar_principal` indica si queda alguna fila pendiente; decide
   cada correo por su propio flag. `cobertura` separa propuestas y pendientes.
7. Continúa con 4.E, 4.G, 4.I, 4.K y el PASO 5 habitual: solo el principal decide
   y ejecuta movimientos ya autorizados por el usuario o la rutina configurada.
   Una simulación solicitada sigue sin mover nada. `permitir_movimientos: false`
   significa que **el adaptador no concede permisos ni mueve**; en híbrido
   `requiere_simulacion: false` permite continuar el flujo habitual, no saltarse
   sus confirmaciones, registro, `montar-mover`, `verificar-sesion` ni deshacer.
   Ante errores de validación o permisos de ese flujo, detener movimientos.

El ahorro del híbrido es una posibilidad, no una medición: evita la evaluación
completa duplicada en casos aceptados, pero sigue necesitando revisión principal.
El principal aporta el contexto local; TypeSafe recibe los mismos campos mínimos
que en comparación. Los presupuestos de llamadas siguen siendo por invocación.

Los temporales sanitizados usan directorio 700 y archivo 600 y se eliminan al
terminar, incluso si hay errores. No guardar propuestas sin aceptar en telemetría o aprendizaje. En híbrido,
las decisiones finales y los movimientos reales usan el registro habitual; solo
las correcciones humanas alimentan aprendizaje.
El script no escribe archivos ni tiene herramientas del buzón. Una ausencia de
PyYAML impide esta delegación: el modo mental no puede sustituir la validación.

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

Tarifa publicada para `jev-1.13.0` y `jev-1.14.0`: **0,042 USD por millón de tokens de
entrada; salida gratuita** (fecha anterior; comprobar cambios en /models).
100 000 tokens de entrada serían 0,0042 USD, aparte del coste del principal.
El consumo procede de `usage`; un timeout/error puede haber consumido tokens.
`coste_total_desconocido` lo señala y `coste_estimado_usd` será `null`.
Para versiones nuevas sin tarifa verificada se cuentan tokens sin extrapolar precios.
`coste_parcial_con_tarifa_usd` recoge solo las llamadas con tarifa conocida;
no representa el total si hay llamadas desconocidas. Las tarifas llevan fecha de
consulta y no sustituyen la factura.

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

Para validar la calidad del modo híbrido, revisar una muestra etiquetada por una persona que
incluya consultas, spam, contexto insuficiente y correos que necesitan respuesta,
en los idiomas reales del usuario. Medir cobertura, errores por tier, coste y
latencia de extremo a extremo; comparar también los casos abstinentes. El tiempo
HTTP informado no mide el flujo completo ni el ahorro frente al principal.
Estos tests no validan precisión operativa: la activación híbrida es explícita
y conserva la revisión del principal y las autorizaciones existentes.
<!-- i18n:fin -->
