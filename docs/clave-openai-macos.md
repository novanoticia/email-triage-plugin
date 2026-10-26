# Guardar las claves de API en el Mac (capas Decisions y Jev)

Esta guía solo hace falta si quieres activar una de las dos capas opcionales que
envían extractos a otro proveedor:

| Capa | Proveedor | Variable de entorno | Dónde se crea la clave | Guía de la capa |
|---|---|---|---|---|
| **Decisions** | OpenAI | `OPENAI_API_KEY` | <https://platform.openai.com> → **API keys** | [`references/decisions.md`](../plugins/email-triage/skills/email-triage/references/decisions.md) |
| **Jev** | TypeSafe AI | `TYPESAFE_API_KEY` | <https://console.typesafe.ai> | [`references/jev.md`](../plugins/email-triage/skills/email-triage/references/jev.md) |

Son claves **distintas y no intercambiables**: cada capa lee solo la suya. El
plugin las lee de la variable de entorno y nunca de un archivo. En macOS lo más
seguro es guardarlas en el **Llavero** y hacer que Terminal las lea al abrirse:
así no quedan escritas en ningún archivo de texto.

Son cuatro pasos por clave. Lo que va en los recuadros grises se copia tal cual en
Terminal (Aplicaciones → Utilidades → Terminal). Si solo usas una capa, haz solo
los comandos de esa clave.

## 1. Consigue la clave

- **OpenAI (Decisions):** en <https://platform.openai.com> → **API keys** →
  **Create new secret key**. Empieza por `sk-…`. OpenAI solo la enseña una vez; si
  la pierdes, crea otra. Hace falta **saldo o un método de pago en la cuenta de
  API**, que es independiente de una suscripción de ChatGPT: pagar ChatGPT Plus no
  da acceso a la API.
- **TypeSafe (Jev):** en <https://console.typesafe.ai>. La facturación es aparte,
  en TypeSafe.

## 2. Guárdala en el Llavero

**No la pegues en el aviso de contraseña** (`password data for new item`): ese aviso
recorta lo pegado a 128 caracteres. Una clave `sk-proj-` de OpenAI tiene más (164
en una prueba real); la de TypeSafe puede tenerlos o no, así que usa el mismo método
siempre. Una clave guardada a medias hace que el proveedor responda que no es válida
(`invalid_api_key` en OpenAI). Guárdala desde el portapapeles:

**Una clave cada vez, y en este orden.** El portapapeles solo guarda una cosa, y la
orden `security` guarda lo que haya en él **en el momento de pulsar Enter**. Copiar el
comando desde esta guía también usa el portapapeles: si lo ejecutas sin más, se
guardaría el texto del comando en vez de la clave. Y si ejecutas las órdenes de las
dos claves seguidas, ambas quedan con la misma clave (las dos cosas pasaron en
pruebas reales). Por eso, para cada clave:

1. **Copia la línea de comando** de abajo (es una sola línea) y **pégala en
   Terminal sin pulsar Enter**.
2. **Copia la clave** en la web del proveedor, con su botón de copiar.
3. **Vuelve a Terminal y pulsa Enter.** Primero verás la longitud de lo copiado:
   apúntala para el paso 4 (si sale un número pequeño, de unas decenas, lo que había
   en el portapapeles era otra cosa: repite desde el punto 1).

**OpenAI (Decisions)**, clave de platform.openai.com (debe salir más de 128):

```bash
pbpaste | wc -c; security add-generic-password -U -a "$USER" -s OPENAI_API_KEY -w "$(pbpaste)"; pbcopy < /dev/null
```

**TypeSafe (Jev)**, solo después de terminar la anterior, clave de
console.typesafe.ai:

```bash
pbpaste | wc -c; security add-generic-password -U -a "$USER" -s TYPESAFE_API_KEY -w "$(pbpaste)"; pbcopy < /dev/null
```

`-U` sustituye la clave anterior si ya había una con ese nombre; lo último
(`pbcopy < /dev/null`) vacía el portapapeles.

En el historial de Terminal queda `$(pbpaste)` escrito así, nunca la clave. El
único coste es que, durante el instante que tarda el comando, la clave aparece en
sus argumentos y otro proceso de tu mismo usuario podría verla: un riesgo muy bajo
en un Mac personal.

## 3. Haz que Terminal la cargue sola

Ejecuta **una sola vez** la línea de cada clave que hayas guardado: cada vez que la
ejecutas añade la misma línea al final de `~/.zshrc`.

```bash
# OpenAI (Decisions)
echo 'export OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s OPENAI_API_KEY -w 2>/dev/null)"' >> ~/.zshrc
# TypeSafe (Jev)
echo 'export TYPESAFE_API_KEY="$(security find-generic-password -a "$USER" -s TYPESAFE_API_KEY -w 2>/dev/null)"' >> ~/.zshrc
```

Después cierra Terminal y ábrelo de nuevo (o ejecuta `source ~/.zshrc`).

La primera vez, macOS puede preguntar si `security` puede acceder al Llavero:
pulsa **Permitir siempre** para que no vuelva a preguntar.

## 4. Comprueba que funciona, sin mostrar la clave

```bash
echo "OpenAI:   ${#OPENAI_API_KEY} caracteres"
echo "TypeSafe: ${#TYPESAFE_API_KEY} caracteres"
```

Cada número debe coincidir con el que apuntaste en el paso 2 (un `0` es que esa
clave no está cargada). Si usas las dos, comprueba además que no son la misma:

```bash
[ "$OPENAI_API_KEY" = "$TYPESAFE_API_KEY" ] && echo "IGUALES: repite el paso 2, una clave cada vez" || echo "distintas: bien"
```
 Si cambias una clave con Terminal abierto, ejecuta antes
`source ~/.zshrc`: la variable solo se lee al abrir Terminal.

Comprueba además que cada proveedor acepta su clave. Las dos consultas solo piden
la lista de modelos de tu cuenta: no envían texto, así que no consumen tokens de
entrada, que es lo que cobran ambos.

```bash
# OpenAI (Decisions)
curl -s -o /dev/null -w "%{http_code}\n" https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
# TypeSafe (Jev)
curl -s -o /dev/null -w "%{http_code}\n" https://api.typesafe.ai/v1/models -H "Authorization: Bearer $TYPESAFE_API_KEY"
```

Cada una debe responder **`200`**. Un **`401`** significa clave ausente o no válida
(lo documenta [TypeSafe](https://docs.typesafe.ai/api/errors.md); en OpenAI se
comprobó en una prueba real, con `invalid_api_key`). Si sale `401` con una
longitud de 128 exactos, la clave se guardó recortada: repite el paso 2. Con la
clave correcta pero mal cargada, `jev.py` o `decisions.py` responden
`credencial_ausente_o_invalida`; con una clave que el proveedor rechaza, `http_401`.
En ambos casos el triaje sigue con el principal.

## Importante

- **Abre Claude Code desde ese Terminal** (escribiendo `claude`) para que herede las
  variables. Si lo abres desde el Dock o como app de escritorio, puede que no las
  vea. No está comprobado cómo pasan el entorno la app de escritorio ni Cowork: si
  `decisions.py` o `jev.py` responden `credencial_ausente_o_invalida`, lo más
  probable es que la causa sea esa.
- **Nunca pegues una clave** en el chat, en `config-decisions.yaml`,
  `config-jev.yaml` ni en ningún archivo del repositorio. El plugin no la necesita
  en ningún otro sitio.
- **No combines las capas en una sesión:** Decisions, Jev y la delegación nativa son
  alternativas. Si tienes varias activas, el modelo te preguntará cuál usar.
- **Pon un límite de gasto** en la web del proveedor si lo ofrece (en OpenAI:
  platform.openai.com → **Limits**). Es la protección más sencilla si algo sale mal.
- **Para borrar una clave más adelante:**

  ```bash
  security delete-generic-password -a "$USER" -s OPENAI_API_KEY      # OpenAI
  security delete-generic-password -a "$USER" -s TYPESAFE_API_KEY    # TypeSafe
  ```

  y quita su línea del final de `~/.zshrc` (por ejemplo con `open -e ~/.zshrc`,
  que lo abre en TextEdit).

## Siguiente paso

Con la clave cargada, copia la plantilla de la capa a `~/.email-triage/`
(`config-decisions.yaml` o `config-jev.yaml`), pon `activo: true` y
`acepta_envio_datos: true`, deja `modo: comparar` y empieza con correos ficticios,
sin movimientos: «compara Decisions con el principal usando correos ficticios» o
«compara Jev con el principal usando correos ficticios». El detalle está en la guía
de cada capa (tabla de arriba).

---

*Guía elaborada con asistencia de IA; requiere revisión humana antes de darla por
definitiva. Los menús de platform.openai.com y console.typesafe.ai pueden cambiar
de nombre.*
