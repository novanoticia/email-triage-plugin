# Evaluación del revisor de Mistral con casos reales

Desde el 2026-11-16 el script y el workflow de la evaluación viven en
[novanoticia/mistral-review](https://github.com/novanoticia/mistral-review)
(`scripts/mistral_eval.py`, `.github/workflows/eval.yml`). Este repo conserva
lo que es suyo:

- **Los casos**: `.github/eval/casos.json`, commits del historial de este repo
  (7 positivos, 5 negativos y el control `c1-guarda-invertida`).
- **El workflow que la lanza**: `.github/workflows/mistral-eval.yml`
  (**Actions → Mistral Eval → Run workflow**), con las mismas entradas que
  antes (`repeticiones`, `solo`, `modelo`, `esfuerzo`, `max_salida`) y el
  artefacto `mistral-eval`.

El método, sus límites, cómo añadir un caso y los resultados del
2026-11-15 (con la decisión de usar `zai-glm-5-3-flash`) están en
[docs/evaluacion.md](https://github.com/novanoticia/mistral-review/blob/main/docs/evaluacion.md)
de ese repo.

Para listar los casos y sus objetivos sin llamar a la API, desde la raíz de
este repo y con `mistral-review` clonado al lado:

```bash
python3 ../mistral-review/scripts/mistral_eval.py
```
