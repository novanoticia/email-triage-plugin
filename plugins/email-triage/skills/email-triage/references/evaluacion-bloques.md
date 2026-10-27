<!-- Nuevo en v3.22.14: bloque condicional (solo con `scoring.bloques: true`).
El SKILL.md deja un stub con la condición de entrada y la regla que rige
aunque no se lea esto. -->

**Evaluación por bloques** (opt-in, `scoring.bloques: true`)

Por qué: en 8 de 10 sesiones reales con 30 criterios, evaluar unas 50
unidades de una vez y puntuarlas juntas dejó huella de plantilla. Con bloques,
cada paso es corto y las huellas se miden sobre toda la sesión.

1. Tras el PASO 1.C, reparte las unidades (un hilo es una unidad) en el
   orden en que vas a evaluarlas:
   `echo '{"ids": ["u1", "u2", ...]}' | python3 triage_helpers.py planificar-bloques`.
   Devuelve `bloques` equilibrados de como mucho `tamano_bloque`.
2. Evalúa **solo el bloque 1**, criterio a criterio, y puntúalo con
   `scoring --brief --desglose ~/.email-triage/desgloses/<session_id>.jsonl
   --desglose-append` (también en simulación).
3. Solo entonces lee el bloque 2, y así hasta el último. Puedes repuntuar
   un correo de un bloque anterior: cuenta su última pasada.
4. `scoring` rechaza (`ok: false`) un lote mayor que `tamano_bloque` o una
   llamada sin el desglose acumulado, y no escribe nada. Sigue el plan; no
   lo esquives puntuando de cabeza.
5. Las huellas de cada respuesta miden la sesión entera
   (`huellas_acumuladas`). Si `plantilla_cercana` trae `ids_previos`, aplica
   la regla de las huellas de plantilla del PASO 4: esos correos de bloques
   anteriores también frenan.

Que vayas bloque a bloque no prueba que leas con cuidado: lo vigilan las
huellas acumuladas, no el orden.
