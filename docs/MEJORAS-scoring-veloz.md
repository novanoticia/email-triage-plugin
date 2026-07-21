# Memo de scoring — qué sesga los resultados en modo veloz

Observado en una sesión real (50 correos, todos newsletters, 2026-07-21).
No son bugs: el pipeline es correcto y reproducible. Son decisiones de diseño
que producen un comportamiento distinto del que el nombre "filtro epistémico"
sugiere. Ordenadas por cuánto mueven el resultado.

---

## 1. En veloz, quien decide el tier es el REMITENTE, no la epistémica

Cadena de tres efectos que se combinan:

**(a) `coste_cognitivo` no tiene ningún criterio core.** De los 12 criterios
core, ninguno mapea a ese eje → en veloz `coste_cognitivo` es **siempre 0**. Un
eje muerto. Los 30 criterios completos sí lo alimentan (p. ej. `retorno_atencional`
no es core), pero veloz solo corre los 12 core.

**(b) `calidad_epistemica` satura a +10 con facilidad.** `forward`(+3) +
`argumento_fuerte`(+3) + `entangled alto`(+3) + `sorpresa media`(+1) = +10, que
es el techo del eje. Casi cualquier ensayo bien escrito llega al máximo, así que
ese eje deja de discriminar entre "bueno" y "excelente".

**(c) Con valor y calidad aplanados arriba, el discriminador real pasa a ser
`sender_bulk` (-4 → atenuado a -1 si el remitente está en el historial) más los
boosts de calibración (+2 remitente frecuente, +1 dominio).** Ese swing de 3
puntos entre -4 y -1 fue, en la práctica, **lo único que separó READING_LATER de
ARCHIVE** en la mayoría de los empates.

**Consecuencia honesta:** el modo veloz funciona como un *filtro de reputación de
remitente* con barniz epistémico, no como un filtro epistémico. En mi sesión
acertó (los remitentes que conservas coinciden con lo que te importa), pero es un
acierto por correlación, no porque la epistémica esté decidiendo.

**Opciones (elige, no hace falta todo):**
- Marcar **un criterio de `coste_cognitivo` como core** (p. ej. `retorno_atencional`
  o `ruido_social`) para que el eje deje de estar muerto en veloz.
- Bajar el techo efectivo de `calidad_epistemica` o rebajar pesos: que
  `argumento_fuerte`+`entangled alto`+`forward` no sume ya el máximo. Así el eje
  vuelve a tener rango útil.
- **Asumir el diseño explícitamente**: documentar que veloz ≈ filtro por
  remitente + señales duras, y que la epistémica fina vive en el config normal
  de 30 criterios. Es una decisión legítima, pero que sea decisión y no efecto
  colateral de "core == 12".

## 2. `sender_bulk` es binario y demasiado potente

Todos los correos de una bandeja de newsletters reciben `sender_bulk`. La única
modulación es `remitente_en_historial` (true → -1, false → -4). Ese salto de 3
puntos es binario: un remitente que conservaste UNA vez pesa igual que uno que
conservaste siete veces.

**Mejora:** penalización **graduada por frecuencia en el historial** en vez de
dos valores. P. ej. `-4 + min(conteo_historial, 3)` → 0 conserva: -4; 1: -3;
2: -2; ≥3: -1. Se apoya en datos que la calibración YA calcula (`top_remitentes`
con `conteo`), y elimina el acantilado.

## 3. Semántica de tiers: REVIEW ≠ urgente

REVIEW ("vale la pena leer con atención") se enruta a `carpetas.destino`, que en
un setup habitual el usuario nombra "Urgentes Claude". Resultado real: metí 13
newsletters **no urgentes** en una carpeta llamada "Urgentes". El skill mezcla
"merece lectura" con "urgente".

**Mejora (doc, no código):** en la plantilla de config, sugerir nombrar
`destino` como "Revisar / Leer con atención" y reservar "Urgentes" para
`destino_reply_needed`. O separar conceptualmente los dos en la doc de tiers.

## 4. `sublote_con_cuerpo` está definido pero no se usa

`resiliencia.sublote_con_cuerpo: 15` existe en el config pero el SCRIPT 1 v1 lee
50 de golpe. O lo respetas (ver `mail-consolidado-v2.applescript` + doctrina) o
lo quitas del config para no prometer algo que no ocurre. Prefiero lo primero:
sublotes de 15 son justo lo que hace la lectura sobrevivir a los timeouts.

## 5. Menor: primer veloz no es veloz

Cache-miss de calibración → corre la lectura lenta del historial igual. Avisar al
usuario (ver Regla 4 de la doctrina). Un `calibrar --leer` con `vigente:false`
debería disparar ese aviso automáticamente.

---

### Prioridad sugerida
1. Punto 4 + doctrina de ejecución (robustez — es lo que más duele hoy).
2. Punto 1 (decide qué quieres que sea veloz; hoy es ambiguo).
3. Punto 2 (fácil, se apoya en datos que ya tienes).
4. Puntos 3 y 5 (documentación).
