<!-- Ensayo P3 (v3.20, ROADMAP P3 paso 3). El SKILL.md deja un stub en 4.B
con la condición de entrada y apunta aquí. La capa vive en
config-ensayo-p3.yaml y la fusiona triage_helpers.py. -->

## Ensayo P3 (opt-in)

**Cuándo aplica:** solo si `scoring.ensayo_p3: true` en `config.yaml` y el
scoring corre en modo `determinista`. Con `false` (por defecto) o en modo
`mental`, ignora esta referencia: se evalúan los 30 criterios de siempre.

Es un **ensayo**: no está validado con correos reales y no sustituye a los
criterios actuales hasta que el mantenedor lo decida.

### Cómo se invoca

Añade la capa a la llamada de `scoring` (también en lote y con `--brief`):

```bash
python3 "<ruta-del-skill>/scripts/triage_helpers.py" scoring --config ~/.email-triage/config.yaml --config-ensayo ~/.email-triage/config-ensayo-p3.yaml < ~/.email-triage/tmp/scoring.json
```

Si la copia del usuario no existe, usa la plantilla del repo:
`<ruta-del-skill>/config-ensayo-p3.yaml`. Con modo veloz, pasa también
`--config-veloz`; la capa del ensayo se aplica después.

### Qué cambia en los criterios

Siguen 30 criterios activos y 13 core. **No envíes veredictos** para
`forward_backward_flow` (5), `fake_justification` (26) ni
`third_alternative` (19): están desactivados y el script los ignoraría.
En su lugar evalúa:

- `razonamiento_dirigido` (core, calidad epistémica) — sustituye a 5 y 26:
  - `exploratorio` (+3): explora la decisión con evidencia.
  - `justificacion_legitima` (0): explica una decisión ya tomada y muestra
    por qué. Justificar no es hacer trampa.
  - `racionalizacion` (−3): **solo con evidencia observable** (razones que
    se contradicen, hechos elegidos a medida). Una conclusión al principio
    del correo no basta. Sin evidencia, el veredicto es `no_observable`.
- `alternativas_reales` (valor decisional) — sentido definitivo de 19:
  - `aporta_alternativa` (+3): ofrece una opción útil más allá de A o B.
  - `binario_honesto` (0): plantea A o B y no hay una C viable a la vista.
  - `falso_dilema` (−2): presenta A o B ocultando una opción viable.
- `responsabilidad_personal` (presión de acción):
  - `asignada` (+3): te asigna la acción de forma explícita, o por tu rol
    o una dependencia comprobable.
  - `compartida` (+1): la acción es de varios, tú entre ellos.
  - `solo_informativa` (0): te informan o vas en copia. Una mención o ir en
    CC **no** es `asignada`.

`responsabilidad_personal` no abre REPLY_NEEDED: eso sigue dependiendo solo
de `forzar_reply_needed` (ver 4.C).

### Al presentar

Cuando el ensayo esté activo, dilo una vez al principio del triaje con una
nota breve en tu propio texto y nombra los tres criterios nuevos en las
razones cuando sean los que deciden el tier.
