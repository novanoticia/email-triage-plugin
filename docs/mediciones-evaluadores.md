# Mediciones reales de los evaluadores LLM

Registro de las pruebas con proveedores reales y **correos inventados** (nunca
reales) en modo `hibrido`: cuántas filas llegan a propuesta y por qué vuelven
las demás al principal. Sirve para decidir qué tocar a continuación con datos,
no con impresiones.

Cómo medir (desde la raíz del repositorio clonado, con la clave cargada o, para
Apple, `fm serve` abierto; ver [`claves-api-macos.md`](claves-api-macos.md)):

```bash
PROVEEDOR=gemini python3 scripts/medir_evaluadores.py
PROVEEDOR=apple PAUSA=0 python3 scripts/medir_evaluadores.py
```

El script usa el `config.yaml` plantilla, no toca `~/.email-triage`, no lee el
buzón ni mueve nada. Solo imprime motivos, criterios, tiers y, por correo
inventado, las dudas, las evidencias vacías y el eco esperado frente al recibido.

**Cómo leer los números.** Con 12 o 40 correos y modelos que no responden igual
en cada ejecución, las diferencias de 1-3 filas son ruido. Valen los órdenes de
magnitud y los patrones que se repiten. «Propuestas» suma `propuesta_validada` y
`reevaluar_tier_o_umbral` (esta última también llega al principal con
propuesta, para que la revise).

## Resumen

| Fecha | Proveedor | Versión | Correos | Propuestas | Freno principal |
|---|---|---|---|---|---|
| 2026-10-31 | Gemini `gemini-3.5-flash-lite` | 3.24.3 | 12 | 0 | `scoring_incompleto` (`__no_aplica__`) |
| 2026-10-31 | Gemini | 3.24.4 | 12 | 4 | dudas genéricas, evidencias vacías |
| 2026-10-31 | Gemini | 3.24.4 | 12 | 5 | dudas genéricas, evidencias vacías |
| 2026-10-31 | Gemini | 3.24.5 | 40 | **28** | `eco_distinto` (12) |
| 2026-11-01 | Apple `pcc` (`fm serve`) | 3.25.0 | 40 | 15 | `eco_distinto` (22) |

## Detalle y qué se cambió por cada una

### 1. Gemini, 12 correos, v3.24.3 — 0 de 12

`scoring_incompleto` 5, `evaluador_con_dudas` 5, `eco_distinto` 2. En las 10
filas evaluadas, los mismos 6 criterios no core salían `__no_aplica__`
(`true_rejection`, `privileging_the_hypothesis`, `proper_humility`,
`positive_bias`, `fake_justification`, `fake_optimization_criteria`): no es
juicio caso a caso, sino que esos criterios hablan de argumentos que una factura
no tiene. El freno descartaba filas cuya exclusión no cambiaba el score.

→ **v3.24.4**: un `__no_aplica__` en un no core con una sola opción a 0 puntos se
puntúa así si el score y el tier no cambian (`no_aplica_puntuado_como`).

### 2-3. Gemini, 12 correos, v3.24.4 — 4 y 5 de 12

`scoring_incompleto` desaparece. Quedan dudas (3-4), evidencias vacías (2-3) y
eco (1-2). Las dudas eran todas **datos ausentes que no cambiaban ningún
veredicto** («no se especifica a qué cuenta pertenece el aviso», «no se incluye el
importe exacto…»), porque el prompt decía «si falta información, anótalo en
dudas». Las evidencias vacías, criterios no core contestados «no» sin nada que
citar.

→ **v3.24.5**: el prompt pide dudas solo si impiden elegir y `__no_aplica__`
donde no hay nada que citar. La tolerancia de dudas sigue en 0.

### 4. Gemini, 40 correos, v3.24.5 — 28 de 40

`propuesta_validada` 19, `reevaluar_tier_o_umbral` 9, `eco_distinto` 12. **0
dudas y 0 evidencias vacías**: el cambio de prompt funcionó. Queda el eco.

### 5. Apple `pcc`, 40 correos, v3.25.0 — 15 de 40

`eco_distinto` 22, `reevaluar_tier_o_umbral` 10, `propuesta_validada` 5,
`evaluador_con_dudas` 3. Marca `__no_aplica__` en más criterios que Gemini (17
distintos) y sus 3 dudas vuelven a ser genéricas («sin datos verificables»):
sigue peor la instrucción de v3.24.5. Unos 13 s por correo; sin coste por token.

## Sondas de contrato (antes de escribir un adaptador)

- **Apple `fm serve`** (`scripts/sonda_fm.py`, 2026-11-01): `system` (on-device)
  tiene 4.096 tokens de contexto en total y nuestra petición ocupa unos 4.090 de
  entrada más ~1.400 de salida: no cabe. `pcc` acepta `response_format`
  `json_schema` estricto. `fm serve` responde en streaming salvo `stream: false`.
- **Ollama** (`scripts/sonda_ollama.py`): pendiente de ejecutar en un Mac real.
  Con menos de 24 GB, Ollama usa 4.096 tokens por defecto: arrancar con
  `OLLAMA_CONTEXT_LENGTH=16384 ollama serve`.

## Pendiente: el eco

El eco es ya el freno principal en los dos proveedores (30 % en Gemini, 55 % en
Apple). Hipótesis por comprobar: en la sonda de Apple, el eco empezaba por el
**asunto** del correo («¿Podemos vernos el jueves? Necesito»), mientras que el
ancla esperada sale solo del **cuerpo** (`estado.texto`). Si se confirma con la
salida de `medir_evaluadores.py` (que ya muestra esperado y recibido), el
arreglo es precisar en el prompt de qué campo copiar, no relajar la
comprobación.

---

> Elaborado con asistencia de IA; requiere revisión humana.
