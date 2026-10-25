# Guardar la clave de OpenAI en el Mac (para la capa Decisions)

Esta guía solo hace falta si quieres activar la capa opcional **OpenAI Decisions**
([`references/decisions.md`](../plugins/email-triage/skills/email-triage/references/decisions.md)).
El plugin lee la clave de la variable de entorno `OPENAI_API_KEY` y nunca de un
archivo. En macOS lo más seguro es guardarla en el **Llavero** y hacer que
Terminal la lea al abrirse: así no queda escrita en ningún archivo de texto.

Son cuatro pasos. Lo que va en los recuadros grises se copia tal cual en Terminal
(Aplicaciones → Utilidades → Terminal).

## 1. Consigue la clave

En <https://platform.openai.com> → **API keys** → **Create new secret key**.
Cópiala: empieza por `sk-…`. OpenAI solo la enseña una vez; si la pierdes, crea
otra.

Hace falta tener **saldo o un método de pago en la cuenta de API**. Esa cuenta es
independiente de una suscripción de ChatGPT: pagar ChatGPT Plus no da acceso a la API.

## 2. Guárdala en el Llavero

**No la pegues en el aviso de contraseña** (`password data for new item`): ese aviso
recorta lo pegado a 128 caracteres, y una clave `sk-proj-` tiene más (164 en una
prueba real). La clave quedaría guardada a medias y OpenAI respondería
`invalid_api_key`. Guárdala desde el portapapeles:

1. Copia la clave con el **botón de copiar** de platform.openai.com.
2. Comprueba que el portapapeles la tiene entera (debe salir **más de 128**):

   ```bash
   pbpaste | wc -c
   ```

3. Guárdala (`-U` sustituye la anterior si ya había una) y vacía el portapapeles:

   ```bash
   security add-generic-password -U -a "$USER" -s OPENAI_API_KEY -w "$(pbpaste)"
   pbcopy < /dev/null
   ```

En el historial de Terminal queda `$(pbpaste)` escrito así, nunca la clave. El
único coste es que, durante el instante que tarda el comando, la clave aparece en
sus argumentos y otro proceso de tu mismo usuario podría verla: un riesgo muy bajo
en un Mac personal.

## 3. Haz que Terminal la cargue sola

```bash
echo 'export OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s OPENAI_API_KEY -w 2>/dev/null)"' >> ~/.zshrc
```

Ejecútalo **una sola vez**: cada vez añade la misma línea al final de `~/.zshrc`.
Después cierra Terminal y ábrelo de nuevo.

La primera vez, macOS puede preguntar si `security` puede acceder al Llavero:
pulsa **Permitir siempre** para que no vuelva a preguntar.

## 4. Comprueba que funciona, sin mostrar la clave

```bash
[ -n "$OPENAI_API_KEY" ] && echo "clave cargada" || echo "no hay clave"
```

Debe responder **«clave cargada»**. Para comprobar además que OpenAI la acepta
(no cuesta nada):

```bash
echo ${#OPENAI_API_KEY}
curl -s -o /dev/null -w "%{http_code}\n" https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
```

La longitud debe coincidir con la del paso 2 y la respuesta debe ser **`200`**. Si
sale `401` con una longitud de 128 exactos, la clave se guardó recortada: repite el
paso 2. Si cambias la clave con Terminal abierto, ejecuta antes `source ~/.zshrc`
(o abre una ventana nueva): la variable solo se lee al abrir Terminal.

## Importante

- **Abre Claude Code desde ese Terminal** (escribiendo `claude`) para que herede la
  variable. Si lo abres desde el Dock o como app de escritorio, puede que no la
  vea. No está comprobado cómo pasan el entorno la app de escritorio ni Cowork: si
  `decisions.py` responde `credencial_ausente_o_invalida`, lo más probable es que
  la causa sea esa.
- **Nunca pegues la clave** en el chat, en `config-decisions.yaml` ni en ningún
  archivo del repositorio. El plugin no la necesita en ningún otro sitio.
- **Pon un límite de gasto** en platform.openai.com → **Limits**. Es la protección
  más sencilla si algo sale mal.
- **Para borrarla más adelante:**

  ```bash
  security delete-generic-password -a "$USER" -s OPENAI_API_KEY
  ```

  y quita la línea que añadiste al final de `~/.zshrc` (por ejemplo con
  `open -e ~/.zshrc`, que lo abre en TextEdit).

Con la clave cargada, el siguiente paso está en
[`references/decisions.md`](../plugins/email-triage/skills/email-triage/references/decisions.md):
copiar `config-decisions.yaml` a `~/.email-triage/`, activar `activo` y
`acepta_envio_datos`, y empezar con una comparación de correos ficticios, sin
movimientos.

---

*Guía elaborada con asistencia de IA; requiere revisión humana antes de darla por
definitiva. Los menús de platform.openai.com pueden cambiar de nombre.*
