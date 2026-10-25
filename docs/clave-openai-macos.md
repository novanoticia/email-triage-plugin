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

Escribe esto, **sin pegar la clave en el comando**:

```bash
security add-generic-password -a "$USER" -s OPENAI_API_KEY -w
```

Te pedirá la contraseña (`password data for new item`): pega ahí la clave y pulsa
Enter. Si te la pide otra vez (`retype password`), vuelve a pegarla. Al pegar no se
ve nada en pantalla; es normal.

Si ya tenías una guardada y quieres sustituirla, usa este otro comando: `-U`
tiene que ir **antes** de `-w`, porque `-w` debe quedar el último para que te
pida la clave.

```bash
security add-generic-password -U -a "$USER" -s OPENAI_API_KEY -w
```

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

Debe responder **«clave cargada»**.

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
