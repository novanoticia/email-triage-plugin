# Privacy Policy — Email Triage plugin

_Last updated: 2026-09-27_

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
- **Claude.** To judge each message, Claude receives the sanitized metadata and
  text as part of your conversation. That processing is governed by the terms
  and data controls of the Claude plan you use.
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

## Changes and contact

Changes to this policy are published in this file and recorded in the
repository history. For questions, open an issue at
<https://github.com/novanoticia/email-triage-plugin/issues> or contact the
author through <https://mindandhealth.org>.
