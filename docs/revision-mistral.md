# Revisión de PR con Mistral

El workflow `Mistral PR Review` hace análisis estático del diff; **no ejecuta
tests**. Los tests reales se ejecutan en el workflow de CI. Un resultado
«Sin hallazgos» significa que el modelo no ha identificado defectos, no que
el código esté demostrado correcto.

La cabecera de cada informe enlaza al perfil de
[Mistral AI (@mistralai)](https://github.com/mistralai), proveedor del modelo
identificado en el título. La revisión se ejecuta mediante su API y el
comentario lo publica GitHub Actions del proyecto. Su asistencia se reconoce
en [CONTRIBUTORS.md](../CONTRIBUTORS.md).

## Dónde vive

Desde el 2026-11-16 el código, las pruebas y la documentación detallada viven
en [novanoticia/mistral-review](https://github.com/novanoticia/mistral-review),
compartidos con otros repos. Este repo solo tiene tres workflows cortos que lo
llaman:

| Workflow | Qué hace | Reutilizable que llama |
|---|---|---|
| `mistral-review.yml` | Revisa cada PR. Check `mistral-review / mistral-review`. | `review.yml` |
| `mistral-reply.yml` | Contrasta los hallazgos de otras IAs (Codex, Claude…). | `reply.yml` |
| `mistral-eval.yml` | Evaluación manual con casos reales. | `eval.yml` |

Antes había aquí una copia propia (`.github/scripts/mistral_review.py`,
`mistral_reply.py`, `mistral_eval.py` y sus tests). La historia de cada
decisión —segunda solicitud, cortes por `length`, un informe por commit,
modelos que razonan, contraste de respuestas— está en
[docs/revision.md](https://github.com/novanoticia/mistral-review/blob/main/docs/revision.md)
de ese repo; las referencias `email-triage-plugin#N` son PR de aquí.

## Lo propio de este repo

- **Excluidos** (parámetro `excluded` de los tres workflows): los generados
  `tests/i18n/linea_base.json` y
  `plugins/email-triage/skills/email-triage/i18n/es.yaml`.
- **Guía** (parámetro `guides`): `REVIEW.md` si existe, si no `CLAUDE.md`,
  como antes. El orden por defecto del revisor compartido pone `AGENTS.md`
  delante, y aquí `AGENTS.md` solo resume `CLAUDE.md` para otros agentes.
- **Modelo**: variable de repositorio `MISTRAL_MODEL` (hoy
  `zai-glm-5-3-flash`, decisión del mantenedor del 2026-11-15) y, solo para
  el contraste, `MISTRAL_REPLY_MODEL` opcional.
- **Casos de la evaluación**: `.github/eval/casos.json`, commits de este
  repo. Método y resultados: [evaluación con casos reales](evaluacion-mistral.md).

## Cómo interpretar el resultado y continuar

1. Comprueba que el SHA del comentario coincide con el último commit del PR;
   para varias revisiones del mismo SHA, distingue la ejecución y su intento.
   Los informes anteriores describen su propio commit e intento, no el actual.
2. Lee los escenarios y las comprobaciones pendientes incluso si no hay hallazgos.
   Una cita válida demuestra que el texto existe, no que el defecto sea real.
3. Reproduce los defectos antes de corregirlos. Tras subir el arreglo, espera
   tanto la nueva revisión de Mistral como los tests de CI.
4. Si la respuesta es inválida o falla la API, el check falla. Consulta el
   comentario y el resumen de Actions; puedes usar «Re-run failed jobs».
5. Si no aparece el comentario, consulta el resumen del job: se escribe antes
   de intentar publicarlo. Un fallo de permisos al publicar hace fallar el job.
6. Si no hay clave, el resumen indica «revisión omitida». Los forks no reciben
   secretos de GitHub; el job termina sin error, pero no cuenta como revisión.

Para contrastar un hallazgo anterior de otra IA: **Actions → Mistral Reply to
AI Reviews → Run workflow**, con `pr_number` y `review_comment_id` (el número
de la URL `#discussion_r…` del hallazgo de línea). Mistral solo lee y comenta:
no aplica parches, no crea commits ni fusiona cambios.

La [auditoría del 29 de octubre de 2026](auditoria-mistral-2026-10-29.md)
contrasta los primeros PR con el código histórico y documenta falsos
positivos.
