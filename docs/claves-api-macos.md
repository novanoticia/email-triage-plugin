# Guardar las claves de API en el Mac (Decisions, Jev, OpenRouter y evaluadores LLM)

Esta guía solo hace falta si quieres activar una de las capas opcionales que
envían extractos a otro proveedor:

| Capa | Proveedor | Variable de entorno | Dónde se crea la clave | Guía de la capa |
|---|---|---|---|---|
| **Decisions** | OpenAI | `OPENAI_API_KEY` | <https://platform.openai.com> → **API keys** | [`references/decisions.md`](../plugins/email-triage/skills/email-triage/references/decisions.md) |
| **Jev** | TypeSafe AI | `TYPESAFE_API_KEY` | <https://console.typesafe.ai> | [`references/jev.md`](../plugins/email-triage/skills/email-triage/references/jev.md) |
| **OpenRouter Decisions** | OpenRouter y el proveedor del modelo | `OPENROUTER_API_KEY` | <https://openrouter.ai/settings/keys> | [`references/openrouter.md`](../plugins/email-triage/skills/email-triage/references/openrouter.md) |
| **Evaluadores LLM: Gemini** | Google | `GEMINI_API_KEY` | <https://aistudio.google.com/apikey> | [`references/evaluadores.md`](../plugins/email-triage/skills/email-triage/references/evaluadores.md) |
| **Evaluadores LLM: Mistral** | Mistral AI | `MISTRAL_API_KEY` | <https://console.mistral.ai> → **API Keys** | [`references/evaluadores.md`](../plugins/email-triage/skills/email-triage/references/evaluadores.md) |
| **Evaluadores LLM: OpenAI** | OpenAI | `OPENAI_API_KEY` (la misma de Decisions) | <https://platform.openai.com> → **API keys** | [`references/evaluadores.md`](../plugins/email-triage/skills/email-triage/references/evaluadores.md) |

Cada proveedor usa su propia clave. Guárdala en el Llavero de inicio de sesión
de macOS. Cuando quieras usar el plugin en Claude Code, inicia una sesión desde
Terminal con la clave del proveedor que has elegido. El plugin la lee de una
variable de entorno.

## 1. Consigue la clave

- **OpenAI (Decisions):** en <https://platform.openai.com> → **API keys** →
  **Create new secret key**. Empieza por `sk-…`. OpenAI solo la enseña una vez; si
  la pierdes, crea otra. Hace falta **saldo o un método de pago en la cuenta de
  API**, que es independiente de una suscripción de ChatGPT: pagar ChatGPT Plus no
  da acceso a la API.
- **TypeSafe (Jev):** en <https://console.typesafe.ai>. La facturación es aparte,
  en TypeSafe.
- **OpenRouter:** crea una clave en <https://openrouter.ai/settings/keys>. La
  facturación y el saldo se gestionan en OpenRouter, independientemente de
  OpenAI y TypeSafe. La misma clave sirve al cambiar entre modelos compatibles
  con su API Decisions, incluido `microsoft/microsoft-decision-1`.
- **Gemini (evaluadores LLM):** entra con tu cuenta de Google en
  <https://aistudio.google.com/apikey> → **Create API key** (si te pide un
  proyecto, acepta el que propone o crea uno nuevo). Empieza por `AIza…`. El
  modelo `gemini-3.5-flash-lite` tiene **nivel gratuito**, pero en ese nivel Google
  puede usar lo que envías para mejorar sus productos: úsalo solo con correos
  ficticios. Para correos reales, activa la facturación del proyecto (nivel de
  pago, 0,30 $ y 2,50 $ por millón de tokens de entrada y salida).
- **Mistral (evaluadores LLM):** en <https://console.mistral.ai> → **API Keys** →
  **Create new key**. La facturación es aparte, en Mistral.
- **OpenAI (evaluadores LLM):** es la **misma** `OPENAI_API_KEY` de Decisions; si
  ya la guardaste, no repitas nada.

## 2. Guárdala en el Llavero

1. Abre **Acceso a Llaveros** desde Spotlight y selecciona el llavero **Inicio
   de sesión**. Para ver el nombre corto de tu cuenta del Mac, abre Terminal y
   ejecuta `id -un`.
2. Pulsa **⌘N** para crear un ítem de contraseña. En **Nombre del ítem**,
   escribe la variable de la tabla, por ejemplo `OPENAI_API_KEY`. En **Nombre
   de cuenta**, escribe el nombre corto obtenido en el paso anterior.
3. Pega la clave completa en el campo **Contraseña** y guarda el ítem. Para
   actualizar una clave ya guardada, abre su ítem en **Inicio de sesión**,
   muestra la contraseña y edítala. Reemplaza después el contenido del
   portapapeles copiando texto que puedas dejar ahí.

Si el Llavero pide acceso para `security`, elige **Permitir** para concederlo
solo en esa ocasión. Puedes revisar permisos anteriores en el ítem, en
**Control de acceso**. [Atajos de Acceso a Llaveros](https://support.apple.com/en-ie/guide/keychain-access/kyca699a9058/mac)
y [permisos del Llavero](https://support.apple.com/en-gb/guide/mac-help/kychn002/26/mac/26).

## 3. Comprueba la clave con su proveedor

Si configuraste la carga automática con una versión anterior de esta guía,
elimina de `~/.zshrc` las líneas que añadiste para exportar estas claves
(puedes abrir el archivo con `open -e ~/.zshrc`). Cierra las sesiones de Claude
Code iniciadas con esas variables y abre una ventana nueva de Terminal.

Copia este bloque en Terminal. Tendrás el comando `clave_email_triage`
disponible mientras esa ventana siga abierta.

```bash
clave_email_triage() (
  set +x
  set +a
  unset clave OPENAI_API_KEY TYPESAFE_API_KEY OPENROUTER_API_KEY GEMINI_API_KEY MISTRAL_API_KEY
  LC_ALL=C
  accion=${1:-}
  proveedor=${2:-}
  case "$accion" in
    validar) ;;
    ejecutar) [ "$#" -ge 3 ] || { echo "Falta el comando que se va a ejecutar." >&2; return 2; } ;;
    *) echo "Uso: clave_email_triage {validar|ejecutar} proveedor [comando]" >&2; return 2 ;;
  esac
  cabecera='Authorization: Bearer '
  case "$proveedor" in
    openai)     variable=OPENAI_API_KEY; url=https://api.openai.com/v1/models ;;
    typesafe)   variable=TYPESAFE_API_KEY; url=https://api.typesafe.ai/v1/models ;;
    openrouter) variable=OPENROUTER_API_KEY; url=https://openrouter.ai/api/v1/key ;;
    gemini)     variable=GEMINI_API_KEY
                url=https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite
                cabecera='x-goog-api-key: ' ;;
    mistral)    variable=MISTRAL_API_KEY; url=https://api.mistral.ai/v1/models ;;
    *) echo "Elige openai, typesafe, openrouter, gemini o mistral." >&2; return 2 ;;
  esac
  clave=$(/usr/bin/security find-generic-password -a "$(/usr/bin/id -un)" -s "$variable" -w) || return 1
  case "$clave" in
    ''|*[![:graph:]]*) echo "La clave guardada está vacía o tiene caracteres inválidos." >&2; return 1 ;;
  esac
  if [ "$accion" = validar ]; then
    builtin printf '%s%s\n' "$cabecera" "$clave" |
      /usr/bin/curl --disable --noproxy '*' --proto '=https' --max-time 20 \
        --silent --output /dev/null --write-out '%{http_code}\n' --header @- "$url"
  else
    shift 2
    export "$variable=$clave"
    exec "$@"
  fi
)
```

Ejecuta solo la línea del proveedor que quieres comprobar:

```bash
clave_email_triage validar openai
clave_email_triage validar typesafe
clave_email_triage validar openrouter
clave_email_triage validar gemini
clave_email_triage validar mistral
```

La consulta solo muestra el código HTTP. Entrega la cabecera a curl por la
entrada estándar, sin poner la clave en sus argumentos, y consulta la API del
proveedor sin enviar correo ni solicitar inferencia. El **200** confirma la
autenticación de esa consulta. Un **401** suele indicar una clave ausente,
inválida o revocada. Con Gemini, revisa también la clave ante un **400** y los
permisos del proyecto ante un **403**. Un **404** indica que la ruta o el modelo
no está disponible. Un **000** indica que no se recibió una respuesta HTTP.

## 4. Abre Claude Code con la clave elegida

En la misma ventana de Terminal, escribe la línea siguiente. Sustituye
`openai` por el proveedor que vas a usar.

```bash
clave_email_triage ejecutar openai claude
```

La clave se carga para esa ejecución y sus procesos hijos, incluidos los
comandos que Claude Code lanza para el plugin. Por eso, usa esa sesión para el
triaje y ciérrala al terminar. El plugin necesita heredar la variable del
proceso que lo ejecuta. Este método está pensado para Claude Code iniciado
desde Terminal. La app abierta desde el Dock y Cowork usan entornos propios y
pueden devolver `credencial_ausente_o_invalida` aunque la comprobación anterior
dé **200**.

Configura una capa externa por sesión. Si Claude no recibe la clave o el
proveedor la rechaza, el triaje sigue con el principal.

Mantén la clave fuera del chat, de los archivos de configuración y del
repositorio. Para retirarla, revócala en la web del proveedor y borra su ítem
en **Acceso a Llaveros**.

## Siguiente paso

Con la clave cargada, copia la plantilla de la capa a `~/.email-triage/`
(`config-decisions.yaml`, `config-jev.yaml` o `config-openrouter.yaml`), pon `activo: true` y
`acepta_envio_datos: true`, deja `modo: comparar` y empieza con correos ficticios,
sin movimientos: «compara Decisions con el principal usando correos ficticios» o
«compara Jev con el principal usando correos ficticios». El detalle está en la guía
de cada capa (tabla de arriba).

Para OpenRouter, empieza con «compara OpenRouter con el principal usando correos
ficticios, sin movimientos». El modelo inicial es
`modelo: microsoft/microsoft-decision-1`; cambia solo ese campo para usar otro ID
compatible con Decisions. Activarlo autoriza enviar los extractos a OpenRouter
y al proveedor que sirva ese modelo.

## Apple Foundation Models (sin clave, macOS 27)

Apple no necesita clave ni Llavero: el plugin habla con `fm serve`, un servidor
que macOS 27 trae de serie y que solo escucha en tu propio Mac. Ese servidor
reenvía la petición a **Apple Private Cloud Compute** (modelo `pcc`): los correos
**salen del Mac** hacia Apple, igual que con los demás proveedores. El modelo que
nunca sale del Mac (`system`) no se admite: la petición no cabe en sus 4.096
tokens.

1. **Acepta la licencia y comprueba los modelos** (solo la primera vez):

   ```bash
   sudo fm license
   fm models
   ```

   Debe aparecer `✓ pcc (AFM 3 Cloud)`.
2. **Abre el servidor en una ventana de Terminal y déjala abierta** mientras
   uses el plugin. macOS solo permite `pcc` a un `fm serve` en primer plano:

   ```bash
   fm serve --host 127.0.0.1 --port 8765
   ```

3. **En tu `~/.email-triage/config-evaluadores.yaml`**, pon
   `proveedor: apple` y deja `modelo: ""` (equivale a `pcc`), con `activo` y
   `acepta_envio_datos` en `true`.
4. Para cerrar el servidor, en su ventana: **Ctrl+C**. Si el plugin lo
   necesita y está cerrado, la fila sale `fallo_red_o_timeout` y el resto del
   lote se detiene; no se envía nada a otro sitio.

En la prueba ficticia de abajo, selecciona `proveedor=apple`.

## Ollama (sin clave, sin salir del Mac)

Ollama no necesita clave ni Llavero y el correo no sale del Mac. Instalación,
descarga de modelos, arranque con contexto ampliado y configuración:
[`modelos-locales-macos.md`](modelos-locales-macos.md).

## Prueba ficticia de los evaluadores LLM (Gemini, Mistral, OpenAI, Apple u Ollama)

> Para medir con 40 correos inventados cuántas filas llegan a propuesta y por
> qué vuelven las demás, usa `scripts/medir_evaluadores.py`. Los resultados de
> cada medición están en [`mediciones-evaluadores.md`](mediciones-evaluadores.md).

Sirve para comprobar, **con un correo inventado**, que el proveedor acepta la
petición, que el modelo responde con el nombre esperado y que la respuesta pasa
todas las validaciones, en `comparar` y en `hibrido`. No toca tu
`~/.email-triage/`, no lee el buzón ni mueve nada, y no muestra la clave. Cuesta
céntimos (o nada en el nivel gratuito de Gemini): dos llamadas.

Hace falta el **repositorio clonado**, porque el correo ficticio vive en los
tests, que no viajan con el plugin instalado.

1. **Clona el repositorio** (solo la primera vez). En Terminal:

   ```bash
   cd ~ && git clone https://github.com/novanoticia/email-triage-plugin.git
   ```

2. **Entra en el repositorio.** En Terminal:

   ```bash
   cd ~/email-triage-plugin
   ```

3. **Ejecuta la prueba.** Copia el bloque entero en la misma ventana donde
   definiste `clave_email_triage`. Elige `gemini`, `mistral`, `openai`,
   `apple` u `ollama` en la primera línea.

   ```bash
   proveedor=gemini
   case "$proveedor" in
     apple|ollama) ejecutar=(python3 -) ;;
     *) ejecutar=(clave_email_triage ejecutar "$proveedor" python3 -) ;;
   esac
   "${ejecutar[@]}" "$proveedor" <<'PYTHON'
   import copy, json, os, subprocess, sys, tempfile
   from pathlib import Path

   PROVEEDOR = sys.argv[1]
   sys.path.insert(0, "plugins/email-triage/skills/email-triage/scripts")
   from tests.test_jev import lote  # un correo ficticio; nunca uno real

   script = "plugins/email-triage/skills/email-triage/scripts/evaluadores.py"
   base = Path(tempfile.mkdtemp())  # base aislada: no toca ~/.email-triage
   p, cfg = lote()
   (base / "config.yaml").write_text(json.dumps(cfg), encoding="utf-8")
   for modo, comando in (("comparar", "comparar"), ("hibrido", "evaluar")):
       lote_modo = copy.deepcopy(p)
       if modo == "hibrido":
           for e in lote_modo["emails"]:
               e.pop("principal")
               e["contexto_suficiente"] = True
       (base / "config-evaluadores.yaml").write_text(json.dumps({
           "activo": True, "acepta_envio_datos": True, "modo": modo,
           "proveedor": PROVEEDOR, "max_llamadas": 1}), encoding="utf-8")
       r = subprocess.run([sys.executable, script, comando, "--config", str(base / "config.yaml")],
                          input=json.dumps(lote_modo), capture_output=True, text=True,
                          env=dict(os.environ, EMAIL_TRIAGE_HOME=str(base)))
       d = json.loads(r.stdout)
       print(modo, "| ok:", d.get("ok"), "| llamadas:", d.get("llamadas"),
             "| motivo general:", d.get("motivo", "-"))
       for f in d.get("resultados", []):
           print("   fila", f["id"], "| motivo:", f.get("motivo"),
                 "| modelo_efectivo:", f.get("modelo_efectivo", "-"),
                 "| detalle:", f.get("motivo_detalle", "-"))
   PYTHON
   ```

4. **Lee el resultado.** Salen dos bloques, `comparar` e `hibrido`:

   | Motivo de la fila | Qué significa |
   |---|---|
   | `solo_comparacion` (en `comparar`) | Todo bien: el proveedor respondió y la respuesta pasó todas las validaciones. |
   | `propuesta_validada` o `reevaluar_tier_o_umbral` (en `hibrido`) | Todo bien. Lo segundo solo dice que el principal tendría que revisar ese tier. |
   | `scoring_incompleto` (en `hibrido`) | Funciona: el modelo excluyó algún criterio no core con `__no_aplica__` que no se podía puntuar sin cambiar el resultado y, por seguridad, esa fila vuelve al principal. Desde v3.24.4 las exclusiones equivalentes a la opción a 0 puntos se puntúan así (`no_aplica_puntuado_como`) y ya no frenan. |
   | `evaluador_con_dudas` | Funciona, pero el modelo anotó dudas sobre el correo ficticio. No es un fallo del adaptador. |
   | `credencial_ausente_o_invalida` (con `llamadas: 0`) | Revisa la clave del proveedor con el paso 3 de esta guía. |
   | `http_400` | En Gemini, casi siempre clave inválida; si la clave da `200` en el paso 3, es que Google no acepta la forma de la petición. Guarda el resultado: hay que revisar el adaptador. |
   | `modelo_inesperado` | El proveedor respondió con otro nombre de modelo (por ejemplo, con un sufijo de versión). Guarda el resultado: hay que revisar el adaptador. |
   | `esquema_no_conforme`, `eco_distinto` u otro | La respuesta llegó, pero no pasó una validación. Guarda el resultado: hay que revisar el adaptador (la columna `detalle` no lleva contenido del correo). |

   Puedes compartir este resultado tal cual, por ejemplo en el chat con Claude:
   no contiene la clave ni datos reales.

La base temporal se crea en la carpeta de temporales del sistema y macOS la
limpia por su cuenta; no hace falta borrarla.

---

*Guía elaborada con asistencia de IA; requiere revisión humana antes de darla por
definitiva. Los menús de platform.openai.com, console.typesafe.ai, openrouter.ai,
aistudio.google.com y console.mistral.ai pueden cambiar de nombre.*
