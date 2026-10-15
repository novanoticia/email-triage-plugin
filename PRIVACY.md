# Privacy Policy — Email Triage plugin

_Last updated: 2026-10-15_

Email Triage is an open-source plugin for Claude (Claude Code and Cowork),
published by Pablo Rodríguez López under the Apache-2.0 license. This policy
explains what data the plugin accesses, where that data goes, and what it
stores.

## Summary

- The plugin has **no server of its own**. The author does not receive,
  collect or store any of your data.
- It sends **no analytics or telemetry** to the author or any third party.
- Optional session logs are saved **only on your computer**.

## Data the plugin accesses

To triage your mail, the plugin may read, for the messages it processes:

- sender, subject, date and message identifier;
- the message body, when needed to classify the message;
- the names of source and destination mailboxes or folders;
- any corrections you give it to calibrate future decisions.

## Where the data goes

- **Your email provider.** Mail is read and moved through the mail access you
  have already set up: Mail.app on macOS (via AppleScript, locally on your
  Mac) or an email connector you choose, such as a Gmail connector. When you
  use a connector, data passes through it under that provider's own privacy
  policy. The plugin does not bundle or choose that service; its `.mcp.json`
  declares no servers.
- **Proveedor de IA del cliente.** Para evaluar cada mensaje, el modelo del
  cliente recibe metadatos y texto sanitizados como parte de la conversación.
  En Claude Code/Cowork es la conexión de Claude que ya utiliza el usuario; en
  un cliente compatible de OpenAI, la conexión de ese cliente. Rigen los términos
  y controles de datos de la cuenta, plan y conexión usados.
- **Local scripts.** The plugin's Python scripts run on your computer and make
  no network requests.

## What is stored, and where

If logging is enabled, the plugin writes files under `~/.email-triage/` (or
under the folder set in `EMAIL_TRIAGE_HOME`). These can contain message
metadata, scores, explanations, chosen destinations and your corrections.
Temporary raw message bodies are deleted after they are read.

These files never leave your computer through the plugin. You can view, edit
or delete them at any time, for example by removing the `~/.email-triage/`
folder.

## Your control

- Use dry-run mode ("simulate the triage") to classify without moving any
  message.
- Messages are only moved with your authorization, and every session can be
  undone from its log.
- Uninstalling the plugin and deleting `~/.email-triage/` removes everything it
  stored.

## Alternancia nativa opcional de modelos

Desactivada por defecto. Al activarla, el cliente puede entregar a un subagente
extractos y metadatos sanitizados, contexto mínimo relevante del perfil/proyectos
y criterios de evaluación, dentro del **mismo proveedor y conexión/cuenta** que
ya usa el modelo principal. El plugin exige comprobar esa capacidad; si no se
puede, continúa en el principal. No hereda toda la conversación ni proporciona
credenciales, acceso al buzón o herramientas al evaluador.

Esto puede generar contexto y registros de subagente conservados por el cliente
o proveedor según sus propias condiciones. El plugin no modifica ajustes de
retención, uso para entrenamiento, residencia de datos ni permisos. No garantiza
una política diferente de la que ya tenga la conexión; la aplicación o una
configuración administrada siguen controlando ese procesamiento.

Los archivos temporales de validación/comparación se mantienen en el directorio
de estado con permisos restringidos y se eliminan al terminar. No se añade un
registro persistente de propuestas ni se incorporan desacuerdos entre modelos al
historial de aprendizaje. El modo comparar no mueve mensajes.

No se implementan llamadas API propias, claves adicionales ni envíos a Jev u
otros proveedores. Esa posibilidad queda únicamente documentada para el futuro.
Una ampliación así requeriría su propia configuración y revisión de privacidad.

## Changes and contact

Changes to this policy are published in this file and recorded in the
repository history. For questions, open an issue at
<https://github.com/novanoticia/email-triage-plugin/issues> or contact the
author through <https://mindandhealth.org>.
