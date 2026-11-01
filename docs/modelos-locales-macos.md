# Modelos locales en macOS (Ollama)

Con Ollama, el evaluador LLM corre **en tu propio Mac**: el correo saneado no
sale de él, no hay clave y no hay factura. Es la única opción del plugin con esa
propiedad: Apple `pcc` reenvía a Private Cloud Compute, y OpenAI, Mistral y
Gemini son servicios externos.

El precio es la lentitud. En un MacBook Pro de 16 GB, `qwen3.5` tarda **unos
110 segundos por correo**, así que 40 correos son unos 75 minutos. Sirve para
lotes que dejas corriendo, no para un triaje interactivo.

Lo que dice esta guía está **comprobado en un Mac real** el 2026-11-01 (Ollama
0.40.13, 16 GB, `scripts/sonda_ollama.py` con un correo inventado). Lo que no
está comprobado se marca como tal.

## 1. Instalar Ollama

Elige una de las dos vías:

- **App (recomendada si no usas Homebrew).** Descárgala de
  [ollama.com/download](https://ollama.com/download), ábrela y arrástrala a
  Aplicaciones. La primera vez instala también el comando `ollama`.
- **Homebrew.** En Terminal: `brew install ollama`.

Comprueba la instalación:

```bash
ollama --version
```

Debe responder con un número de versión (la prueba se hizo con la 0.40.13).

## 2. Descargar los modelos

```bash
ollama pull qwen3.5
```

Ocupa unos 7,6 GB. Es el **único modelo que el plugin admite** como evaluador:
es el que se comprobó con la sonda (cumple el esquema estricto y no anota dudas
genéricas). Comprueba que está:

```bash
ollama list
```

Debe aparecer `qwen3.5:latest`.

**Modelos de decisión (opcionales, todavía sin uso en el plugin).** `tev1:4b`
(4,4 GB) y `d1` (3,7 GB) responden con el mismo contrato que Jev en
`/v1/systemone`, pero en la sonda eligieron `__incierto__` en 25 y 7 de 30
criterios, respectivamente: en modo `hibrido` no darían ninguna propuesta. No
hay adaptador para ellos. Solo hacen falta si quieres repetir la sonda:

```bash
ollama pull tev1:4b
ollama pull d1
```

**Espacio y memoria.** Con 16 GB de RAM, cierra aplicaciones pesadas mientras
corre el modelo. `ollama rm <modelo>` borra uno que ya no uses.

## 3. Arrancar Ollama con contexto suficiente

Este paso es el que más fácil se olvida, y sin él no funciona. Con menos de
24 GB de memoria de vídeo, Ollama usa **4.096 tokens de contexto**, y la
petición del plugin ocupa unos 4.150 de entrada más unos 2.000 de salida: se
recortaría sin avisar.

1. **Cierra Ollama del todo**, también el icono de la llama en la barra de
   menús (clic en el icono → *Quit Ollama*).
2. En una ventana de Terminal, déjalo abierto con contexto ampliado:

   ```bash
   OLLAMA_CONTEXT_LENGTH=16384 ollama serve
   ```

   Deja esa ventana abierta mientras uses el plugin. Para pararlo: **Ctrl+C**.
3. **Carga el modelo** desde otra ventana de Terminal (no contesta nada; solo
   lo sube a memoria):

   ```bash
   ollama run qwen3.5:latest ""
   ```

4. **Comprueba el contexto**:

   ```bash
   ollama ps
   ```

   La columna de contexto debe decir **16384**. Si dice 4096, Ollama no se
   arrancó con la variable: vuelve al punto 1.

Desde v3.26.1 el plugin hace esa misma comprobación antes del primer correo
(consulta `/api/ps`, solo lectura, solo en `127.0.0.1`) y **no envía ninguno**
si el modelo no está cargado o su contexto no basta. Por eso el paso 3 es
necesario: Ollama solo dice el contexto de un modelo ya cargado, y lo descarga
tras 5 minutos sin uso. Si pasa ese tiempo, repite el paso 3.

> **No comprobado:** la app de Ollama tiene un ajuste de longitud de contexto
> en su configuración que haría innecesario el paso 2. Si lo usas, verifica
> igualmente con `ollama ps`.

Ollama escucha solo en `127.0.0.1:11434`, tu propio Mac. El plugin habla solo
con esa dirección, sin clave y **sin pasar por el proxy** del sistema; no
acepta otro destino.

## 4. Activarlo en el plugin

En tu `~/.email-triage/config-evaluadores.yaml` (si no existe, copia la
plantilla `config-evaluadores.yaml` del plugin):

```yaml
activo: true
acepta_envio_datos: true
modo: comparar        # empieza comparando; hibrido cuando confíes en él
proveedor: ollama
modelo: ""            # vacío = qwen3.5:latest
max_llamadas: 5
timeout_segundos: 300 # Ollama admite hasta 600; los demás, hasta 60
```

`acepta_envio_datos` se exige aunque nada salga del Mac. El plugin no puede
saber qué hace el servidor que escucha en ese puerto, así que mantiene el mismo
doble consentimiento que con los demás proveedores.

## 5. Probarlo con correos inventados

Desde la carpeta del repositorio clonado, con `ollama serve` abierto como en el
paso 3:

```bash
python3 scripts/sonda_ollama.py                          # 1 correo, ~2 min
PROVEEDOR=ollama PAUSA=0 python3 scripts/medir_evaluadores.py   # 40 correos, ~75 min
```

Ninguno de los dos toca tu `~/.email-triage/`, lee el buzón ni mueve nada. Los
resultados se registran en [`mediciones-evaluadores.md`](mediciones-evaluadores.md).

## Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `fallo_red_o_timeout` en todas las filas y `llamadas: 0` | `ollama serve` no está abierto (la comprobación previa no llegó a `/api/ps`) | Abre el paso 3 |
| `fallo_red_o_timeout` en una fila y el resto detenido | El correo tardó más que `timeout_segundos`, u Ollama seguía generando una petición abandonada (la API no permite detectarlo) | Desde v3.26.2 cada respuesta tiene un tope de 3.450 tokens (unos 190 s), así que no debería repetirse con `timeout_segundos: 300`; si pasa, súbelo hasta 600. Si acabas de cortar una ejecución, reinicia `ollama serve` (Ctrl+C y vuelve a lanzarlo) antes de la siguiente |
| `contexto_insuficiente` en todas las filas | El modelo está cargado con menos contexto del necesario (la salida trae `preflight` con las dos cifras). Suele ser la app de la barra de menús, que arrancó su propio servidor con 4.096 | Cierra la app (*Quit Ollama*) y vuelve al paso 3 |
| `modelo_no_cargado` en todas las filas | `qwen3.5:latest` no está en memoria (no se cargó, o pasaron 5 minutos sin uso) | `ollama run qwen3.5:latest ""` y repite |
| `contexto_no_verificable` | Tu versión de Ollama no informa del contexto en `/api/ps` | Actualiza Ollama |
| `modelo_no_verificado` | `modelo` distinto de `qwen3.5:latest` | Déjalo vacío |
| `modelo_inesperado` | Ollama respondió con otro modelo | `ollama list`; vuelve a hacer `ollama pull qwen3.5` |
| `esquema_no_conforme` o respuestas cortadas | Contexto de 4.096 | `ollama ps`; vuelve al paso 3 |
| `limites_invalidos` | `timeout_segundos` mayor de 600 | Bájalo |
| El Mac va muy lento | El modelo ocupa unos 8 GB de memoria | Cierra otras apps; usa lotes pequeños |

## ¿Y LM Studio?

[LM Studio](https://lmstudio.ai) también sirve modelos en local con una API
compatible con Chat Completions (por defecto en `127.0.0.1:1234`). **El plugin
todavía no lo admite**: no se ha sondeado si su servidor acepta el esquema
estricto ni cómo responde con nuestra petición. Queda apuntado en el
`ROADMAP.md`. `scripts/sonda_ollama.py` no sirve para probarlo: empieza por
rutas propias de Ollama (`/api/version`, `/api/tags`), y LM Studio usa otros
nombres de modelo. Haría falta una sonda propia antes de escribir el adaptador.

---

> Elaborado con asistencia de IA; requiere revisión humana.
