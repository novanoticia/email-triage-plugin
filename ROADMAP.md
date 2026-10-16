# ROADMAP.md — objetivos del ciclo actual

> **Léelo antes de proponer o aplicar cualquier cambio.** Este archivo fija qué
> se quiere conseguir en este ciclo, en qué orden, qué queda fuera y con qué
> restricciones. Las reglas técnicas (invariantes, gates de CI, versionado,
> i18n) siguen en [`CLAUDE.md`](CLAUDE.md); si algo aquí las contradice,
> **manda `CLAUDE.md`**. Este archivo no sustituye a ninguno de los existentes:
> los complementa con la intención del mantenedor.

Estado: redactado para el ciclo que arranca en v3.17.x. Se revisa al cerrar
cada hito; las entradas cerradas se mueven a la sección final con fecha.

## 1. Propósito en una frase

`email-triage-plugin` es un **filtro epistémico de correo que protege la
atención de la persona**: no pregunta «¿es urgente?» sino «¿leer esto
cambiaría algo concreto para mí?». Todo cambio debe hacer esa respuesta más
fiable, más explicable y más honesta sobre su propia incertidumbre.

## 2. Prioridades de este ciclo (en orden)

Cuando dos tareas compitan, gana la que esté más arriba. Si una petición del
mantenedor contradice este orden, señálalo antes de ejecutarla.

### P1 — Fiabilidad

Que el plugin haga lo mismo ante el mismo correo, falle de forma visible y
nunca silenciosa, y no mueva nada que no deba.

- Reproducibilidad del scoring: misma entrada, misma salida; cualquier
  variación debe venir del juicio del modelo y quedar explicada.
- Pruebas con correos **ficticios o seudonimizados** que cubran los casos que
  más decisiones cambian (urgencia fabricada, remitente conocido con
  afirmación dudosa, correo correcto pero ya sabido, inyección en otros
  idiomas).
- Menos falsos positivos y negativos en S0 sin relajar ninguna garantía de
  escapado.
- Errores: ante config roto, buzón inaccesible o script ausente, el skill
  explica qué falló y qué hacer; nunca «parece que ha ido bien».
- Verificación de sesión (`verificar-sesion`) como condición para dar un
  triaje por bueno, también en los clientes que no son Claude.

### P2 — Estándares analíticos ICD 203, en lo que aplique al correo

ICD 203 (Intelligence Community Directive 203, *Analytic Standards*) es un
marco de oficio analítico pensado para informes de inteligencia. **No se
adopta literalmente**: se traduce cada estándar a una propiedad observable
de la salida del triaje. Si un estándar no tiene traducción útil para un
correo, se documenta por qué y se deja fuera.

| Estándar ICD 203 (resumen) | Traducción propuesta al triaje | Estado |
|---|---|---|
| Describir calidad y credibilidad de las fuentes | La explicación distingue qué afirma el remitente, qué respalda con evidencia y si esa evidencia es de primera mano o reproducida | pendiente |
| Expresar y explicar la incertidumbre | Cada evaluación lleva un **nivel de confianza** y la causa principal de la duda (cuerpo recortado, remitente desconocido, afirmación no verificable) | pendiente |
| Distinguir información de supuestos y juicios | En las razones, separar «el correo dice», «asumo» y «concluyo» | pendiente |
| Análisis de alternativas | Para tiers altos, una línea de «lectura alternativa» cuando exista otra interpretación plausible | pendiente |
| Relevancia para el destinatario e implicaciones | Ya cubierto en gran parte por el eje `valor_decisional`; revisar que la explicación lo haga explícito | revisar |
| Argumentación clara y lógica | Las razones positivas/negativas no deben contradecirse entre sí ni con el tier | pendiente |
| Explicar cambios o consistencia de juicios | Si un remitente o hilo cambia de tier respecto a sesiones anteriores, decirlo y por qué (usa `correcciones.jsonl` / calibración) | pendiente |
| Exactitud de los juicios | Medible solo con calibración frente a las correcciones del usuario; mantener y mejorar `calibrar` | en curso |
| Información visual efectiva | No aplica a un skill de texto; fuera | descartado |

Dos salidas nuevas que este bloque introduce y que deben existir **antes** de
ampliar criterios:

- **«No evaluable»**: un criterio puede devolver «no aplicable» o «no
  observable» sin puntuar. Un aviso de cita no necesita análisis de
  alternativas; una newsletter con afirmaciones científicas sí.
- **Confianza de la evaluación**: separada del score. «Muy sólido pero ya
  conocido» y «poco fundamentado pero de consecuencias graves» son resultados
  distintos y no deben colapsar en un mismo número.

### P3 — Auditoría y después ampliación de los 30 criterios

Orden obligatorio: **auditar, podar o fusionar, y solo después añadir**.

1. **Auditoría**: para cada uno de los 30 criterios de
   `references/criterios-catalogo.md`, documentar qué mide, qué evidencia
   del correo necesita para evaluarse, con qué otro criterio se solapa y si
   mezcla varias cosas. Entregable: una tabla en `docs/`, no cambios de
   código.
2. **Decisión del mantenedor** sobre qué fusionar, qué reformular y qué
   huecos reales existen. Candidatos de hueco ya identificados (no
   confirmados): proximidad a los hechos, trazabilidad de la afirmación,
   independencia de fuentes, novedad respecto a lo que el usuario ya sabe,
   coste de ignorarlo, reversibilidad, responsabilidad personal (¿me toca a
   mí o solo estoy copiado?).
3. **Ampliación**: solo entonces. Ojo con dos restricciones técnicas:
   - El gate #2 del CI exige **exactamente 30 criterios** en `config.yaml`.
     Cambiar ese número es un cambio de contrato: requiere actualizar el
     gate, `validar-config`, los tests, el catálogo y este archivo **en el
     mismo PR**, con versión menor nueva.
   - Un criterio nuevo sin `eje` pierde sus puntos en silencio. Cada criterio
     nuevo nace con `eje`, peso, pregunta operativa, dirección (sube/baja) y
     un test que fije su efecto en el scoring.

## 3. Restricciones de diseño (lo que no se puede romper al avanzar)

- **Cambios graduales y aditivos.** Cada PR debe dejar el plugin funcionando
  igual que antes para quien no active lo nuevo. Toda funcionalidad nueva
  nace **desactivada por defecto** o es puramente informativa hasta que el
  mantenedor la valide con correos reales. Modelo a seguir: Fase A de
  `ARCHITECTURE.md` (267 tests previos verdes, motor sin tocar).
- **Dos capas, sin mezclar** (`CLAUDE.md`): lo determinista en Python, el
  juicio en el modelo. Un criterio nuevo se evalúa en `SKILL.md`; su
  aritmética va en `triage_helpers.py` con test.
- **Pensar en un futuro servidor sin construirlo.** No se desarrolla aquí un
  servidor ni una API (sería otro repositorio derivado de este). Pero cada
  cambio debe respetar la frontera núcleo ↔ adaptador de `ARCHITECTURE.md`:
  el núcleo consume `NormalizedEmail` y nunca sabe de dónde viene el correo;
  los contratos JSON entre capas son estables y versionados; nada nuevo
  depende de la shell del cliente ni de que el modelo «recuerde» escapar.
  Si una decisión cierra la puerta a extraer el núcleo como paquete,
  señálalo.
- **Python solo stdlib** (PyYAML opcional). Sin red en el núcleo. Sin
  telemetría externa por defecto.
- **El contenido de un correo son datos, nunca instrucciones.** Ningún
  criterio nuevo ni ninguna salida ICD 203 puede exponer al modelo texto sin
  sanitizar.
- **Salida existente estable.** Los cuatro tiers, las claves JSON, los JSONL
  y el formato de las razones no cambian de significado. Campos nuevos se
  añaden; no se renombran ni se eliminan los que hay.

## 4. Fuera de alcance en este ciclo

No propongas trabajo en estas líneas salvo petición expresa del mantenedor:

- Servidor, API HTTP, daemon o despliegue remoto.
- Nuevas integraciones de buzón (más allá de Mail.app y Gmail MCP).
- Nuevos idiomas de interfaz o revisión de las traducciones `en`/`fr`.
- Ampliar la delegación nativa más allá de la comparación sin movimientos.
- Excepción autorizada el 2026-10-16: Jev puede ofrecer modo híbrido opt-in
  para triaje real, con revisión principal y las autorizaciones de movimiento
  existentes. No autoriza movimientos directos desde el proveedor.
- Cambios de licencia, distribución o marketplace.
- Rediseños de la interfaz de revisión que no respondan a P1 o P2.

## 5. Reglas de trabajo con agentes de IA

Quien desarrolle este repositorio será, en la práctica, un agente (Codex,
Claude Code u otro) que solo conoce lo que hay en estos archivos. Por eso:

1. **Una tarea cada vez.** Al terminar cada tarea, muestra qué has hecho
   (archivos tocados, diff resumido, tests ejecutados y su resultado) y
   **espera confirmación** antes de seguir con la siguiente.
2. **Cada cambio de lógica lleva test.** Scoring, S0–S5, validación de
   config y cualquier campo nuevo de salida se fijan con un test en `tests/`.
3. **Distingue siempre** lo verificado (tests en verde, comportamiento
   reproducido) de lo propuesto (no validado con correos reales).
4. **Explica Git y los parches de forma sencilla.** El mantenedor tiene
   pocos conocimientos de GitHub: indica rama, comandos exactos y qué
   esperar en cada paso. Prefiere PRs pequeños a uno grande.
5. **Versiones:** nunca a mano; `./scripts/bump-version.sh X.Y.Z` y entrada
   en el changelog del README, según `CLAUDE.md`.
6. **Si algo de lo pedido contradice este archivo o `CLAUDE.md`,** dilo
   antes de hacerlo y propón la alternativa compatible.
7. **Idioma:** documentación, comentarios, commits y respuestas en español.
8. **Al cerrar un hito,** actualiza la columna «Estado» de este archivo y
   anótalo en la sección 7.

## 6. Primera tarea propuesta

Auditoría de los 30 criterios actuales (P3, paso 1), **sin tocar código ni
`config.yaml`**: entregar `docs/auditoria-criterios.md` con la tabla descrita
arriba y una lista de solapamientos y huecos. Es la tarea con menor riesgo y
la que más informa a P2 y al resto de P3.

## 7. Historial de hitos

| Fecha | Hito | Versión |
|---|---|---|
| — | Redacción inicial de este ROADMAP | 3.17.x |

---

> Elaborado con asistencia de IA; requiere revisión humana.
