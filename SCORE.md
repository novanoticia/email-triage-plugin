# Evaluación de Calidad del Repositorio — email-triage-plugin

> **Informe generado con asistencia de IA.** Todos los hallazgos han sido
> verificados contra el código fuente con trazabilidad exacta de archivo y línea.
> Este análisis es informativo: revisa cada punto antes de actuar sobre él.

---

## Diagnóstico ejecutivo

El plugin es conceptualmente sólido y está bien documentado para su tipo
(plugin de Claude sin código compilado). El marco epistémico de 30 criterios
es original y funcionalmente coherente. Sin embargo, presenta **un bug crítico
de parsing YAML** que afecta a 15 de los 30 criterios y que pasaría
desapercibido en un uso superficial, junto con deuda técnica acumulada en
scripts de instalación, ausencia total de tests y algunas inconsistencias
entre archivos.

---

## Puntuación por dimensión

| Dimensión | Puntos | Nota |
|-----------|--------|------|
| Diseño y arquitectura | 8 / 10 | Marco epistémico coherente y bien estructurado |
| Calidad del código | 5 / 10 | Bug crítico en YAML; placeholders incorrectos |
| Documentación | 8 / 10 | Extensa y útil; pequeñas inconsistencias internas |
| Cobertura de tests | 1 / 10 | Sin tests de ningún tipo |
| Seguridad | 7 / 10 | Sin secretos en código; gaps en scripts de shell |
| Mantenibilidad | 5 / 10 | Versión dispersa; single-maintainer; sin CI/CD |
| Fiabilidad en producción | 6 / 10 | Buenas defensas en SKILL.md; bugs en config silenciosos |

### **Puntuación global: 6 / 10**

---

## Hallazgos críticos

### 1. Colisión boolean YAML — 15 criterios afectados

**Severidad: CRÍTICA · Archivo: `plugins/email-triage/skills/email-triage/config.yaml`**

Las claves `no:` sin comillas son interpretadas como `False` (boolean) por los
parsers YAML 1.1 (PyYAML, yq, y la mayoría de herramientas). Cualquier lookup
programático del valor `"no"` devolvería `KeyError`.

Líneas afectadas: 205, 215, 261, 287, 303, 332, 342, 350, 367, 375, 392, 418,
426, 434, 460.

Criterios afectados: `cambia_algo_concreto`, `cambio_predicciones`,
`confusion_productiva`, `abre_opciones`, `agente_estrategico`,
`relevancia_longitudinal`, `motivated_stopping`, `motivated_continuation`,
`third_alternative`, `privileging_the_hypothesis`, `positive_bias`,
`semantic_stopsigns`, `fake_justification`, `fake_optimization_criteria`,
`absence_of_expected_evidence`.

```yaml
# Estado actual — se parsea como {False: -5}
cambia_algo_concreto:
  si: 5
  no: -5

# Correcto — clave string explícita
cambia_algo_concreto:
  si: 5
  "no": -5
```

### 2. Placeholder incorrecto en `usuario.perfil`

**Severidad: ALTA · Archivo: `config.yaml` · Líneas: 26-31**

El campo `perfil` usa block scalar (`|`) con texto instructivo como valor
literal. La validación `len(perfil) >= 10` de SKILL.md (línea 691-692)
siempre pasa porque el texto de instrucciones tiene más de 10 caracteres.
El usuario podría instalar el plugin sin rellenar su perfil y obtener triaje
genérico sin ninguna advertencia.

```yaml
# Estado actual — el texto instructivo ES el valor del campo
perfil: |
  # ⚠️ OBLIGATORIO (mínimo 10 caracteres) — Describe tu rol...

# Correcto — valor vacío, instrucciones en comentario YAML
# ⚠️ OBLIGATORIO (mínimo 10 caracteres) — Describe tu rol,
# formación e intereses en 2-4 líneas.
perfil: ""
```

### 3. Lista `proyectos_activos` con placeholders vacíos

**Severidad: MEDIA · Archivo: `config.yaml` · Líneas: 33-36**

El valor por defecto `['', '']` hace que cualquier comprobación `if proyectos_activos:`
sea verdadera aunque el usuario no haya rellenado el campo. Debería ser `[]`.

```yaml
# Estado actual — truthy aunque esté vacío
proyectos_activos:
  - ""
  - ""

# Correcto
proyectos_activos: []
```

---

## Hallazgos de deuda técnica

### 4. Versión hardcodeada en múltiples ficheros

**Severidad: BAJA · Archivos:**
- `plugins/email-triage/.claude-plugin/plugin.json` · línea 3
- `scripts/install-plugin.sh` · línea 7
- `fix-cowork-version.sh` · línea 11
- `plugins/email-triage/skills/email-triage/SKILL.md` · líneas 3, 36

No existe una fuente única de versión. Cada release requiere actualizar al
menos 4 archivos manualmente, con riesgo de inconsistencias.

### 5. Seguridad en `scripts/install-plugin.sh`

**Severidad: BAJA · Archivo: `scripts/install-plugin.sh`**

- Línea 34: `rm -rf "$PLUGIN_DIR/$PLUGIN_NAME"` sin comprobar que
  `$PLUGIN_NAME` no sea una cadena vacía o contenga rutas relativas.
- Sin comprobación de plataforma: el script usa rutas macOS hardcodeadas
  (`$HOME/Library/Application Support/Claude/`) pero no verifica que se
  ejecuta en macOS antes de proceder.

### 6. Inconsistencia documental: umbral del tier `archive`

**Severidad: BAJA · Archivos: `config.yaml` línea 126; `SKILL.md` línea 461**

`config.yaml` documenta `archive: -1` con el comentario "Todo lo que quede
por debajo va a archive", sugiriendo que el score ≤ -1 → archive.
`SKILL.md` tabla de tiers indica `score < 0` como condición de archive.
La frontera efectiva es `< reading_later`, pero el desacuerdo entre archivos
puede confundir al usuario que quiera calibrar los umbrales.

---

## Ausencias destacadas

| Elemento | Impacto |
|----------|---------|
| Sin tests (unitarios, integración, contrato) | Cualquier cambio en `config.yaml` o `SKILL.md` es ciego |
| Sin CI/CD (GitHub Actions) | No hay validación automática en PRs |
| Sin `CHANGELOG.md` | El historial de cambios está solo en el README |
| Sin `CONTRIBUTING.md` | Barrera de entrada para colaboradores |
| Sin validación de schema YAML | Errores en `config.yaml` solo se detectan en ejecución |

---

## Recomendaciones priorizadas

### Quick wins (< 1 hora cada una)

1. **Comillar las 15 claves `no:`** en `config.yaml` — elimina el bug crítico
   de YAML boolean sin riesgo de regresión.

2. **Corregir `perfil` y `proyectos_activos`** — cambiar el block scalar del
   perfil a `""` y la lista a `[]` para que los valores por defecto sean
   semánticamente vacíos.

3. **Añadir guardia de plataforma** en `install-plugin.sh`:
   ```bash
   if [[ "$(uname -s)" != "Darwin" ]]; then
     echo "⚠️  Este script solo funciona en macOS" && exit 1
   fi
   ```

4. **Añadir guardia de no-vacío** antes del `rm -rf` en `install-plugin.sh`
   línea 34:
   ```bash
   [[ -n "$PLUGIN_NAME" ]] || { echo "❌ PLUGIN_NAME vacío"; exit 1; }
   ```

### Cirugía estructural (requieren planificación)

5. **Fuente única de versión** — leer la versión de `plugin.json` en los
   scripts con `python3 -c "import json; ..."` en lugar de mantenerla
   duplicada en 4 ficheros.

6. **Schema de validación YAML** — añadir un `schema.yaml` (jsonschema o
   Cerberus) para `config.yaml` y un script de validación local, más un
   GitHub Action que lo ejecute en cada PR.

7. **Tests de humo** — aunque el plugin no tiene código ejecutable en Python
   o JS, se puede añadir un test que cargue `config.yaml` con PyYAML y
   compruebe que todos los campos de `criterios_epistemicos` tienen el tipo
   correcto (int, no bool), y otro que valide que SKILL.md no referencie
   campos inexistentes en `config.yaml`.

---

## Potencial de mejora asistida por IA

| Tarea | Automatizable con IA |
|-------|---------------------|
| Comillar las 15 claves `no:` | ✅ Sed/regex de una línea |
| Generar schema JSON de `config.yaml` | ✅ Altamente automatizable |
| Generar tests de validación YAML | ✅ Altamente automatizable |
| Refactorizar versión a fuente única | ✅ Con contexto del repo |
| Añadir CI/CD básico (GitHub Actions) | ✅ Template estándar |

---

*Análisis realizado sobre el commit `75bf9c9` (rama `main`, 4 de abril de 2026).*
*Herramienta: github-plugin-analyzer · Asistido por Claude.*
