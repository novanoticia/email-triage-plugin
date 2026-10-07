# Catálogos de idioma (i18n)

> Elaborado con asistencia de IA; requiere revisión humana.

Esta carpeta contiene lo que el skill `email-triage` muestra a la persona, una
frase por clave y un fichero por idioma. Los tres idiomas actuales son `es`
(referencia, idioma por defecto), `en` y `fr`. Las traducciones `en` y `fr` las ha
escrito una IA y están en estado `borrador-ia`: **ninguna está revisada por una
persona**.

## Cómo se elige el idioma

Con una marca explícita en el mensaje: `idioma=en` o `lang=fr`. Un código suelto
(`en`, `es`) no cuenta. Sin marca se lee `usuario.idioma` de `config.yaml`; sin eso,
español. `scripts/idioma.py` aplica esa regla (y la tabla de casos está en
`tests/test_idioma.py`).

## Formato de un catálogo (`<código>.yaml`)

```yaml
estado: borrador-ia        # referencia | borrador-ia | experimental | revisado
redactado_por: IA
revisado_por: null         # un idioma sin revisor no puede figurar como «revisado»
frases:
  resumen.titulo:
    texto: "…"             # literal que el modelo copia tal cual
    origen: original       # original | nuevo
    fuente: "SKILL.md:938"
    riesgo: normal         # alto = confirma mover, archivar o deshacer: revisión humana obligatoria
    lista: false           # true: las opciones separadas por « / » deben coincidir en número
    invariable: false      # true: el texto puede ser igual al de es
```

Lo que va entre corchetes dentro de un `texto` (`[Asunto]`, `[destino]`) es un hueco
que redacta el modelo; el número de huecos debe coincidir entre idiomas. Los tiers
(`REPLY_NEEDED`, `REVIEW`, `READING_LATER`, `ARCHIVE`), los modos, las claves JSON y
lo que va entre comillas invertidas **no se traducen**.

## Cómo añadir un idioma

1. Copia `en.yaml` a `<código>.yaml` (código de 2 o 3 letras, p. ej. `pt.yaml`).
2. Traduce cada `texto`. Deja `estado: borrador-ia` y `revisado_por: null`.
3. Añade tu idioma a cada término de `glosario.yaml`.
4. Valida: `python3 scripts/i18n_validar.py` (desde la raíz del repositorio). Te dice
   qué clave falta, qué hueco no coincide o qué término del glosario no se aplicó.
5. No edites `es.yaml` a mano: se regenera con `python3 scripts/i18n_extraer.py generar`
   a partir de los textos originales.

No hay que tocar ningún otro fichero: el idioma se descubre solo.

## Qué no cubre

- La detección de inyección S0 cubre **solo español e inglés** y **no cambia con
  `idioma=`**: es una propiedad del idioma del correo recibido, no de la interfaz.
- El texto libre que redacta el modelo (resúmenes, razones, notas) no está revisado.
- Los mensajes de error de los scripts siguen en español.
