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

## Cuándo se ejecuta

Al crear el PR, marcarlo listo para revisión, subir commits, reabrirlo o editar
su título o descripción. Cada ejecución que obtiene un resultado publica un
**comentario nuevo**, identificado con el SHA de la cabeza del PR y un enlace
a la ejecución y al intento de Actions. Los reintentos del mismo commit también
se conservan por separado, incluidos los resultados inválidos o fallos de API.
Los comentarios anteriores no se editan ni se borran. Un push nuevo cancela
la revisión en curso; una ejecución cancelada antes de publicar puede no dejar
comentario. Editar el PR también puede volver a consumir la API.

## Qué recibe y qué debe devolver

- Guía `REVIEW.md`, o `CLAUDE.md` si no existe la primera; máximo 20.000 caracteres.
- Título, descripción y diff con diez líneas de contexto, hasta 150.000 caracteres.
- Contexto de los archivos Python cambiados, leído con `git show` del commit:
  hasta 10.000 caracteres por archivo y 40.000 en total. No ejecuta el código.
  Los recortes se indican; no se incluyen automáticamente dependencias sin cambios.
- Entre una y seis comprobaciones con archivo, escenario, conclusión y estado
  `revisado` o `pendiente`. Son razonamientos por lectura, no pruebas ejecutadas.
  Sus rutas se contrastan con el inventario de Git, incluidos renombrados puros,
  cambios de permisos y binarios sin hunks. Esto no valida la verdad del análisis.
- Hallazgos solo con escenario concreto y una cita literal del diff del archivo.
  Se admite que no haya hallazgos; una respuesta sin comprobaciones es inválida.

El modelo se elige con la variable de Actions `MISTRAL_MODEL` (por defecto
`codestral-latest`). La clave se configura como secreto `MISTRAL_API_KEY`.

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

Las pruebas locales simulan la API. La calidad de detección debe contrastarse
en PR reales, especialmente con regresiones conocidas que antes no detectó.

La [auditoría del 29 de octubre de 2026](auditoria-mistral-2026-10-29.md)
contrasta los primeros PR con el código histórico, documenta falsos positivos
y propone una evaluación de calidad antes de nuevos ajustes del revisor.
