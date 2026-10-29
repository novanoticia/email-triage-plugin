<!-- i18n:inicio -->
# OpenAI Decisions opcional: comparación y triaje híbrido

Segundo clasificador externo, con **las mismas garantías, modos y frenos que Jev**
(`references/jev.md`): ambos usan el núcleo común `scripts/clasificadores.py` y
solo cambian el transporte y el formato. Esta capa es independiente de
`config-modelos.yaml` y de `config-jev.yaml`. Su ausencia o `activo: false`
conserva el flujo habitual. `comparar` (por defecto) fuerza simulación durante
toda la sesión, incluso con errores. `hibrido`, elegido explícitamente por el
usuario, permite integrar veredictos validados en el flujo real. Una petición de
simulación siempre prevalece sobre híbrido. Si el modo no se puede determinar por
un archivo ilegible o inválido, detener la delegación y mantener simulación;
nunca deducir autorización de movimiento.

**No combinar Decisions con Jev ni con el evaluador nativo en la misma sesión.**
Un único evaluador alternativo por sesión: si hay varias capas activas, pregunta
cuál usar y no ejecutes las demás. Así la comparación y el coste son atribuibles.

## Activación y credenciales

Usa la base de estado resuelta por el PASO 0 (normalmente `~/.email-triage`). Copia
allí la plantilla `config-decisions.yaml`, fuera del repositorio, solo cuando el
usuario quiera activarlo. Requiere ambos `activo: true` y `acepta_envio_datos: true`.
Antes de activarlos, explica qué se enviará a OpenAI y que hay facturación
independiente. Un archivo inválido desactiva la delegación; no corregirlo
activando permisos.

La clave se crea en la plataforma de API de OpenAI (<https://platform.openai.com>)
y se inyecta en el entorno del proceso como `OPENAI_API_KEY` mediante el gestor de
secretos del cliente. No pedir pegarla en el chat, guardarla en YAML/git, pasarla
por argumentos, imprimirla ni registrar el entorno. **Es una credencial distinta**
de la delegación nativa (que no usa claves propias del plugin) y de
`TYPESAFE_API_KEY` (Jev): ninguna sustituye a otra, y una suscripción de ChatGPT
no es una clave de API. En macOS, la guía paso a paso para guardarla en el
Llavero y cargarla en Terminal está en <https://github.com/novanoticia/email-triage-plugin/blob/main/docs/clave-openai-macos.md>
(no viaja con el plugin instalado: da la URL); si la persona pregunta cómo
configurarla, remítela ahí, sin pedirle la clave.
El host necesita Python con PyYAML y HTTPS a
`api.openai.com`. Si no puede, informa de la limitación y conserva el principal;
no simular una llamada real mediante otro modelo.

La configuración admite `modo: comparar` (defecto) o `modo: hibrido`, `modelo`
(`gpt-6-luna` por defecto, el único admitido por la API al consultarla), máximo de
llamadas por ejecución 1–50 (defecto 5), timeout 1–60 s (defecto 15) y confianza
mínima 0–1 (defecto 0,8). No admite endpoints alternativos. Otro ID de modelo
solo se acepta si la persona lo escribe en su capa; no hay alias: el `model` de la
respuesta debe coincidir exactamente con el solicitado o el correo vuelve al
principal (`modelo_inesperado`). El informe identifica `modelo_solicitado` y
`modelo_efectivo` por correo. Desactivar o retirar el archivo revierte la
integración sin cambiar el scoring.

## Comparación: protocolo del orquestador

Idéntico al de Jev (pasos 1–6 de `references/jev.md`), cambiando solo el script y
la capa:

1. Mismas reglas de lectura, sanitización S0–S5 y controles del principal. Lote
   pequeño, preferentemente ficticio primero. Mismo extracto (≤1500 caracteres) y
   mismo perfil mínimo para ambos evaluadores, sin conversación heredada.
2. `python3 scripts/decisions.py preparar` con el mismo JSON por stdin (`id`
   ordinal local, `asunto`, `remitente`, `cuerpo`). Local y sin red.
3. El principal añade `principal` y `control` exactamente como en Jev, sin tocar
   `estado`, `huella`, `s0` ni `id`. Los controles nunca se delegan.
4. `python3 scripts/decisions.py comparar --config RUTA_CONFIG_PERSONAL
   --config-decisions RUTA_CAPA`, con `--config-veloz` y `--config-ensayo` en los
   mismos casos que en Jev.
5. La respuesta siempre indica `usar_principal: true` y
   `permitir_movimientos: false`, también ante fallos. Un bloqueo S0/cap no sale a
   la red. `proveedor: "openai_decisions"`; `evaluacion_decisions` conserva
   veredictos, abstenciones y probabilidades validadas.
6. Presenta discrepancias, exclusiones, llamadas, duración HTTP y consumo. El
   principal es referencia, no verdad etiquetada. Decisions no devuelve
   evidencias narrativas: no inventarlas.
7. Mismo diagnóstico por criterio que Jev (punto 7 de `references/jev.md`,
   v3.22.5): `por_criterio` por fila, `comparacion_por_criterio` en la salida y
   `motivo_detalle` en los rechazos de forma, solo en `comparar` e informativo;
   desde v3.22.21 también `tasa_coincidencia_equivalente` (par `no` de 0
   puntos / `__no_aplica__`, ver el mismo punto de `jev.md`).
8. Misma tolerancia a dudas opt-in que Jev (`tolerancia_dudas`, punto 8 de
   `references/jev.md`, v3.22.22), con el mismo freno en `clasificadores.py`.
9. Misma regla de capa en disco que Jev (punto 9 de `references/jev.md`,
   v3.22.23) con `config-decisions.yaml` y `--config-decisions`.
10. Misma propuesta sin freno en `comparar` (punto 10 de `references/jev.md`,
   v3.22.25): `propuesta_sin_freno` y `comparacion_sin_freno`, solo informativas.

## Triaje real: modo híbrido explícito

```yaml
activo: true
acepta_envio_datos: true
modo: hibrido
modelo: gpt-6-luna
```

Se aplica el mismo protocolo híbrido que Jev (pasos 1–7 de `references/jev.md`)
con `python3 scripts/decisions.py evaluar --config RUTA_CONFIG_PERSONAL
--config-decisions RUTA_CAPA`: `contexto_suficiente` sin `principal`, reevaluación
de `ARCHIVE`, `REPLY_NEEDED`, distancia ≤1 a un umbral y discrepancias de
confianza, revisión obligatoria con `usar_principal: false`, `payload_scoring` en
4.D y el PASO 5 habitual. El adaptador no concede permisos ni mueve correos.

## Contrato y validación

Verificado en la documentación oficial el **25 de octubre de 2026**:
<https://developers.openai.com/api/docs/guides/decisions> y
<https://developers.openai.com/api/reference/resources/decisions/methods/create>.

`POST https://api.openai.com/v1/decisions`, Bearer en Authorization, JSON con
`model`, `input`, `questions` y `prompt_cache_options: {"mode": "explicit"}` sin
breakpoints, que según la referencia **desactiva la caché**: sin escrituras (más
caras que la entrada normal) ni extractos retenidos en ella. Una petición por correo: `input` es un texto con
`perfil_minimo` y el extracto sanitizado (`correo`), compartido por todas las
preguntas. No se usan imágenes, `input_json` ni historial de conversación. Cada
criterio activo es una pregunta `choice` con `name` igual al criterio,
`instructions` con la pregunta real y `choices` `{value, description}` con sus
opciones originales, `__incierto__` y, solo en los condicionales,
`__no_aplica__` (las mismas descripciones que Jev; la API recomienda una opción
de escape). No se usan `predicate` ni `score`. No se envían pesos, carpetas,
controles ni historial.

La lista `answers` se convierte a la forma interna común antes de validarla. Se
exige cobertura exacta: un `name` por pregunta, sin nulos ni duplicados; tipo
`choice` sin campos extra; valores de texto (la API admite booleanos, que aquí se
rechazan); probabilidades sin valores repetidos, finitas, que sumen uno (con la
misma tolerancia de redondeo que Jev, v3.22.6) y con la opción elegida como máxima. **Un `refusal` en cualquier pregunta es abstención del
correo entero** (`decisions_refusal`): la API permite que el resto se responda,
pero no se puntúa con criterios ausentes. La confianza declarada es independiente
de la distribución: se recalcula `(max(p)-1/n)/(1-1/n)` y se usa el **menor** de
ambos valores, señalando discrepancias; nunca se aumenta. No es probabilidad de
acertar. Los veredictos pasan por el mismo `cmd_scoring_dispatch`; no hay score
del proveedor. Sin reintentos ni redirecciones; errores HTTP/red detienen las
llamadas restantes y se reducen a su código numérico, sin cuerpo HTTP.

## Costes y privacidad

Tarifa publicada para `gpt-6-luna` en `/v1/decisions`: **0,10 USD por millón de
tokens de entrada sin caché; salida sin coste** (consulta del 2026-10-25).
100 000 tokens de entrada serían 0,01 USD, aparte del coste del principal.
Con la caché desactivada todo el input se cobra a esa tarifa; si la respuesta
informa tokens de caché pese a ello, el coste pasa a desconocido. La estimación
**no incluye** el recargo de procesamiento regional (+10 % según la página de
precios) ni multiplicadores de contexto largo (`coste_excluye_recargos: true`):
puede quedarse corta, no es una cota superior.
Un timeout o error puede haber consumido tokens: `coste_total_desconocido` y
`coste_estimado_usd: null`. Un modelo sin tarifa guardada cuenta tokens sin
extrapolar precio. No sustituye la factura.

Activar esta capa envía a **OpenAI, otro proveedor**, asunto, remitente y extracto
sanitizados, perfil mínimo y preguntas de evaluación. Sanitizar **no anonimiza
datos personales**. La clave solo viaja en la cabecera de autenticación.

La API Decisions admite **Zero Data Retention** y procesamiento regional en Europa
(EEE + Suiza) para **clientes elegibles**, con acuerdos y condiciones de la
cuenta. **No se da por activado**: depende de la cuenta de API de quien configure
la capa y el plugin no puede comprobarlo ni pedirlo. El procesamiento regional
puede tener recargo. El plugin no cambia los ajustes de privacidad del proveedor
principal; añade un destinatario y condiciones al habilitar esta opción.

## Pruebas y alcance inicial

`python3 -m unittest tests.test_decisions -v` usa correos ficticios y transporte
simulado: no requiere claves, no usa red ni gasta crédito. Incluye una prueba de
equivalencia: la misma respuesta expresada en formato Jev y en formato Decisions
produce la misma forma interna y el mismo scoring. Verifica el mecanismo, no la
precisión ni la compatibilidad real de la API. La primera comprobación real
necesita clave propia y consentimiento explícito; pedir «compara Decisions con el
principal usando correos ficticios, sin movimientos».

Para validar la calidad del híbrido rigen las mismas condiciones que en Jev: una
muestra etiquetada por una persona, en los idiomas reales del usuario, midiendo
cobertura, errores por tier, coste y latencia de extremo a extremo.
<!-- i18n:fin -->
