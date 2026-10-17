# Ensayo P3 — resultados con correos ficticios (G.7)

Fecha: 2026-10-17 · Versión del plugin: 3.20.0 · ROADMAP, P3 paso 3.

Este informe compara el scoring **base** (plantilla `config.yaml`) con el
**ensayo** (la misma plantilla + la capa `config-ensayo-p3.yaml`) sobre los
ocho correos ficticios de `tests/ensayo_p3/correos.yaml`. Los veredictos los
etiquetó a mano el agente y los aprobó el mantenedor.

## Método

- **Qué se compara.** Cada correo lleva veredictos `comunes`, iguales en las
  dos configuraciones, y los específicos de cada una:
  - `base`: los criterios 5, 19 y 26;
  - `ensayo`: sus sustitutos.

  Así la diferencia aísla el efecto de la capa.
- **Cómo se calcula.** Con el motor determinista real: `cmd_scoring`, sin red
  y sin modelo. El contrato P2 se enciende solo para leer la cobertura; no
  altera score ni tier.
- **Cómo se reproduce:** `python3 scripts/ensayo_p3_comparar.py --markdown`.
  Un test (`tests/test_ensayo_p3_comparacion.py`) exige que la tabla de abajo
  sea idéntica a la salida del script.

## Resultados

| Correo | Base | Ensayo | Δ | Ejes saturados |
|---|---|---|---|---|
| Cita sin argumento | 20 REPLY_NEEDED | 23 REPLY_NEEDED | +3 | — |
| Plantilla con obligación | 12 REVIEW | 15 REVIEW | +3 | — |
| Informe sólido ya conocido | 2 READING_LATER | 2 READING_LATER | +0 | valor_decisional |
| Afirmación grave sin pruebas accesibles | 2 READING_LATER | 8 **REVIEW** | +6 | calidad_epistemica, valor_decisional |
| Copia sin responsabilidad | -1 ARCHIVE | -1 ARCHIVE | +0 | valor_decisional |
| Aviso que cancela uno anterior | 19 REVIEW | 20 REVIEW | +1 | valor_decisional |
| Exploración abierta con datos | 34 REPLY_NEEDED | 37 REPLY_NEEDED | +3 | valor_decisional |
| Falso dilema comercial | -20 ARCHIVE | -20 ARCHIVE | +0 | calidad_epistemica, presion_accion, valor_decisional |

Resumen: de 8 correos, **1 cambia de tier**, 5 suben, 0 bajan y 3 quedan
igual. «Ejes saturados» son los ejes que alguna de las dos configuraciones
recorta a su rango.

## Hallazgos

**Verificado (lo dicen los números):**

1. **La fusión de 5 y 26 elimina el doble cómputo.** En «Afirmación grave sin
   pruebas» la base suma −12 en calidad epistémica: −2 por el criterio 5 y −3
   por el 26, sobre la misma impresión. El ensayo suma −7. Como el eje se
   recorta a −10, de esos +5 solo se ven +3. Los otros +3 del Δ vienen de
   `responsabilidad_personal: asignada`.
2. **`responsabilidad_personal` es el motor casi único del cambio.** Aporta
   +3 en la cita, la plantilla y la exploración, y +1 en la cancelación. Sube
   lo que es mío y deja quietos la copia y el informe ajeno. No hay ningún
   correo que baje.
3. **La saturación oculta parte del efecto.** `valor_decisional` llega a su
   tope en 6 de los 8 correos. En el «Falso dilema», calidad epistémica pasa
   de −17 a −15 sin recortar, pero los dos quedan en −10: el ensayo resta
   distinto y no se nota. Es el hallazgo D de la auditoría, que el ROADMAP
   lleva a P1, visto en un caso concreto.
4. **Un solo cambio de tier, y es el discutible.** «Afirmación grave sin
   pruebas», un correo con aspecto de phishing, pasa de READING_LATER a
   REVIEW.
5. **La cobertura P2 detecta un hueco en ese mismo correo.** Con el ensayo,
   `razonamiento_dirigido` queda como core sin explicar: no hay evidencia de
   racionalización y el veredicto se omitió. `references/ensayo-p3.md` pide
   en ese caso `no_observable`. Habría que hacerlo así, aunque no cambia
   ningún número.

**Propuesto (juicio, pendiente de decisión del mantenedor):**

- **El cambio de tier del correo 4 parece defendible.** REVIEW significa
  «léelo con atención», no «créetelo». Contra el phishing protegen S0, que
  capa a REVIEW si detecta inyección, y los criterios 23, 28 y 30, que ya
  penalizan la falta de pruebas. No debería protegerlo una penalización doble
  por razonamiento dirigido sin evidencia.
- **Vigilar la inflación por responsabilidad.** Si en correos reales casi
  todo resulta `asignada`, el criterio dejaría de discriminar. Antes de
  activarlo por defecto conviene ver su distribución real.
- **La saturación merece su propio trabajo (P1)** antes de añadir más
  criterios: hoy el tope de los ejes decide más que los criterios.

## Límites de este ensayo

- **Muestra pequeña.** Ocho correos ficticios no son una muestra
  estadística; ilustran mecanismos.
- **Quien etiqueta es el agente.** Los veredictos son juicios suyos,
  aprobados por el mantenedor. No miden si un modelo real elegiría esos
  mismos veredictos ni con qué consistencia.
- **Falta probar el flujo completo** de lectura de correo, sanitización y
  presentación. Para eso, el mantenedor puede ejecutar un triaje en modo
  simulación con `scoring.ensayo_p3: true` y `scoring.modo: determinista`.

## Siguiente paso propuesto

1. Prueba en simulación con correos reales y comparación del tier con y sin
   la capa.
2. Según el resultado, decidir si el ensayo pasa a la configuración por
   defecto. Eso cambiaría el contrato de 30 criterios en `config.yaml` y
   exigiría gate, `validar-config`, catálogo y versión menor en el mismo PR.

> Elaborado con asistencia de IA; requiere revisión humana.
