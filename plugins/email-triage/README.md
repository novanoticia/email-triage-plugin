# Email Triage

![Icono de Email Triage](./icon.png)

Email Triage ayuda a clasificar correo electrónico con 30 criterios de
racionalidad bayesiana. Evalúa el valor decisional, la calidad epistémica, el
riesgo de manipulación, el coste cognitivo y la presión de acción, y propone
cuatro destinos: `REPLY_NEEDED`, `REVIEW`, `READING_LATER` y `ARCHIVE`.

## Qué hace

- Lee metadatos y, cuando hace falta, cuerpos de mensajes mediante las
  capacidades de correo que ya tenga configuradas el cliente: Mail.app en
  macOS, un conector de Gmail u otro proveedor compatible.
- Sanitiza el contenido antes de analizarlo para reducir el riesgo de
  inyección de instrucciones desde un correo.
- Calcula puntuaciones reproducibles con scripts locales de Python y explica
  cada clasificación.
- Puede mover mensajes solo cuando el usuario lo autoriza; el modo simulación
  no mueve mensajes.
- Puede guardar, de forma local y configurable, registros de sesión,
  puntuaciones, explicaciones y correcciones para calibrar decisiones futuras.

## Datos que utiliza y dónde van

El plugin puede acceder al remitente, asunto, fecha, identificador y contenido
de los correos necesarios para realizar el triaje. También puede usar las
carpetas de origen y destino y las correcciones que aporte el usuario.

El plugin no incluye un servidor remoto, no incorpora analítica remota y no
envía telemetría a su autor. Sus scripts deterministas procesan los datos
localmente; para realizar el juicio epistémico, Claude recibe los metadatos y
el texto del correo después de la sanitización, como parte de la conversación
del usuario. Ese procesamiento queda sujeto a los términos y controles de
datos del plan de Claude con el que se ejecute el plugin. Los registros
opcionales se guardan en el equipo del usuario, bajo
`~/.email-triage/` (o en `EMAIL_TRIAGE_HOME` cuando se configura), y pueden
contener metadatos, puntuaciones, explicaciones, destinos y correcciones. Los
cuerpos crudos temporales se eliminan después de su lectura.

Si el usuario elige Mail.app, el acceso y los movimientos ocurren mediante
AppleScript en su Mac. Si elige Gmail u otro conector externo, los datos
necesarios pasan por ese conector y quedan sujetos a la política de privacidad
del proveedor que el usuario haya configurado. El plugin no empaqueta ni
selecciona ese servicio: su archivo `.mcp.json` no declara servidores.

## Requisitos

- macOS para la integración con Mail.app mediante AppleScript, o un conector de
  correo compatible configurado por el usuario.
- Python 3.9 o posterior para los scripts deterministas. El núcleo usa la
  biblioteca estándar; PyYAML es opcional para validar la configuración.

El plugin no usa lanzadores `npx` ni `uvx` y no instala paquetes al ejecutarse.

## Seguridad y control

El contenido del correo se trata como datos, nunca como instrucciones. Los
message IDs se escapan antes de interpolarlos en AppleScript, los movimientos
se construyen mediante el pipeline seguro del plugin y cada sesión puede
verificarse contra su registro. Antes de usarlo sobre una bandeja real, se
recomienda empezar con «simula el triaje».

## Licencia y código fuente

Apache-2.0. Código fuente, documentación completa e incidencias:
[novanoticia/email-triage-plugin](https://github.com/novanoticia/email-triage-plugin).

Autor: Pablo Rodríguez López. Esta versión se preparó con asistencia de
ChatGPT (OpenAI); el historial completo de contribuciones está documentado en
el repositorio de código fuente.
