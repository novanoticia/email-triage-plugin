<!-- Extraído de SKILL.md en v3.28.1: bloque condicional que solo hace falta
cuando hay correcciones aprendidas. El SKILL.md deja un stub con la condición
de entrada en el PASO 0.B y en el 4.A.3, y apunta aquí. -->

# Ajustes aprendidos (PASO 0.B y 4.A.3)

## PASO 0.B — Cargar ajustes aprendidos de correcciones anteriores

Ejecutar DESPUÉS de leer `config.yaml` y ANTES de conectar al proveedor.

**Vía preferente (NUEVO en v3.4)**: si existe `scripts/triage_helpers.py`
en la carpeta del skill (junto a este SKILL.md), ejecutarlo con Desktop
Commander y usar su salida JSON directamente como tabla de ajustes — el cálculo es determinista y no
depende de aritmética mental:

```bash
python3 "<ruta-del-skill>/scripts/triage_helpers.py" ajustes
```

Devuelve `ajustes_remitente`, `ajustes_dominio`, `ajustes_keyword` y
`deriva` (si la hay, comunicar la sugerencia al usuario sin aplicarla).
Si el script falla o no existe, aplicar el procedimiento manual siguiente.

**Higiene del historial (opcional, NUEVO en v3.8.9)**: `correcciones.jsonl`
es append-only. La lectura ya está acotada a las últimas 5000 líneas, pero el
fichero en disco crece indefinidamente. Cuando supere ~10 MB (o de tanto en
tanto), recórtalo de forma atómica con el subcomando `compactar` — conserva las
últimas N líneas (las que la lectura consume igualmente) y es no-op por debajo
del tope:

```bash
python3 "<ruta-del-skill>/scripts/triage_helpers.py" compactar          # recorta a 5000
python3 "<ruta-del-skill>/scripts/triage_helpers.py" compactar --dry-run  # solo reporta
```

**Vía manual (fallback)**: lee `~/.email-triage/correcciones.jsonl` con
Desktop Commander y calcula ajustes dinámicos que se superpondrán a los
pesos estáticos del config durante esta sesión.

Si el archivo no existe o está vacío: continuar sin ajustes aprendidos.
No es un error — simplemente no hay historial de correcciones todavía.

### Procedimiento manual (fallback)

La especificación completa del cálculo (decay temporal, direcciones de
corrección, umbrales por remitente/dominio/keyword, deriva, resumen) vive
en `references/paso-0b-manual.md` — leerla con Desktop Commander SOLO si
`triage_helpers.py` no está disponible. El script implementa exactamente
esa especificación.

---

## 4.A.3 — Ajustes aprendidos (PASO 0.B) — aplicar después de 4.A.1 y 4.A.2

Si PASO 0.B produjo una tabla de ajustes dinámicos, aplicarlos ahora
(en modo determinista también van sumados dentro de `extra_points`,
nunca como claves de `hard_rules`):

| Fuente | Puntos | Condición |
|--------|--------|-----------|
| **Remitente aprendido (boost)** | +2 o +3 | Corregido consistentemente hacia arriba |
| **Remitente aprendido (penalización)** | -2 o -3 | Corregido consistentemente hacia abajo |
| **Dominio aprendido (boost)** | +1 | Dominio con patrón de subida |
| **Dominio aprendido (penalización)** | -1 | Dominio con patrón de bajada |
| **Keyword aprendida (boost)** | +1 | Keyword correlacionada con correcciones UP |
| **Keyword aprendida (penalización)** | -1 | Keyword correlacionada con correcciones DOWN |

**Reglas de precedencia**:
- Un ajuste aprendido NO puede convertir un remitente de `ignorar` (-99) en
  evaluable — las reglas de bloqueo total son inmunes al aprendizaje
- Un ajuste aprendido puede sobrepasar a `remitentes_prioritarios` si hay
  suficiente evidencia contraria (≥ 5 correcciones DOWN con peso ≥ -5)
- Los ajustes aprendidos se muestran en el desglose del score como
  `[aprendido]` para distinguirlos de las reglas estáticas

**En el desglose de puntuación**, mostrar los ajustes aprendidos
explícitamente:

```
📊 Puntuación: 6
   Extra (calibración): +1 (dominio frecuente)
   Aprendido:  +2 (remitente corregido 4 veces hacia arriba)
   Epistémico: +3 (valor_decisional +2, calidad_epistemica +1)
```
