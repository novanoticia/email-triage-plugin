# Diseño: aprender de «Archivados», de los VIP de Mail y de «Conservar»

Estado: **aprobado el 2026-11-02**, con D1–D4 aceptadas y D5 rechazada (ver
«Decisiones del mantenedor»). Fase 0 en curso: `scripts/sonda_vip.py`.
Redactada el 2026-11-02 a partir de su descripción de cómo usa las carpetas.

## El problema

El triaje solo aprende de una carpeta: `carpetas.historial` («Conservar» en la
plantilla). En el PASO 2, `calibrar` lee los **últimos 100** correos (remitente
y asunto), saca los **10 remitentes** más frecuentes, y un remitente masivo que
esté entre ellos pasa su B de −4 a −1. Hay tres huecos:

1. **«Conservar» guarda sobre todo newsletters que gustan.** Con 100 correos y
   10 remitentes, una newsletter conservada pocas veces no cuenta.
2. **Lo importante de verdad está en «Archivados»**: respuestas de personas,
   facturas, licencias y claves. Esa carpeta no entra en el triaje y el triaje no
   la conoce. Un correo de alguien de la universidad puede acabar en `ARCHIVE`.
3. **Mail.app ya tiene una lista de remitentes importantes: los VIP.** El triaje
   no la lee.

Las carpetas tienen funciones distintas y **no se mezclan**: «Conservar» es lo
que gusta (sobre todo newsletters) y «Archivados» es lo que importa (de todo
menos newsletters).

## La propuesta: dos historiales con efectos distintos

| Fuente | Qué enseña | Qué se lee | Efecto en el triaje |
|---|---|---|---|
| «Conservar» (ya existe) | remitentes que gustan | remitente y asunto, como hoy | atenúa la B; ampliado en la fase 3 |
| «Archivados» (nueva, opcional) | remitentes importantes | **solo la dirección del remitente** | el correo no baja de un tier mínimo **[D1]** |
| VIP de Mail.app (nueva, opcional) | remitentes importantes | **solo las direcciones VIP** | igual que «Archivados», o más fuerte **[D2]** |

### Lo que no se hace, y por qué

- **Nunca se leen cuerpos ni asuntos de «Archivados».** Ahí hay licencias y
  claves: un asunto como «Tu clave de licencia ABCD-…» ya es un secreto. Solo se
  extrae la dirección del campo `From`.
- **Nada sale del Mac.** La lectura es AppleScript, el cálculo es Python y la
  lista se queda en `~/.email-triage/`. No se envía a ningún modelo ni API, ni en
  modo `hibrido` ni en delegación.
- **El modelo no decide quién es importante.** Lo decide el script, igual que
  `prioritario` desde v3.21.27: el payload de `scoring` trae `remitente` y el
  script lo coteja con la lista.
- **No hay coincidencia por nombre visible ni por dominio genérico.** Se coteja
  la dirección exacta con `_direccion` y `_casa_remitente`: sin el `+sufijo`,
  parseada por estructura y nunca por el nombre visible. Un dominio como
  `@gmail.com` nunca entra entero **[D3]**.
- **No se aprende del contenido** («newsletters parecidas»). Comparar textos
  exige leer cuerpos, y eso es otra conversación de privacidad. Queda para
  después.

### Riesgo: remitentes suplantados

Un phishing puede falsificar el `From` de alguien de «Archivados». El efecto
propuesto es solo un **tier mínimo**: el correo no se archiva, pero tampoco
gana confianza ni pasa a `REPLY_NEEDED`. Si S0 detecta inyección, su cap
(`REVIEW`) manda sobre el suelo, como ya hace con `suelo_prioritarios`. Que un
phishing con remitente falso acabe en `REVIEW` ante una persona es aceptable;
que se archive en silencio el correo de alguien importante, no.

## Detalle técnico

**Config (aditivo, nace desactivado).** Sin estas claves, el comportamiento es
el de hoy.

```yaml
carpetas:
  historial_importante: null     # p. ej. "Archivados"
filtros:
  remitentes_vip_mail: false     # true: leer los VIP de Mail.app
  suelo_importantes: "REVIEW"    # [D1]: REVIEW o READING_LATER
```

**Lectura (AppleScript, solo direcciones).** Un script nuevo en `references/`
devuelve una dirección por línea. El nombre de la carpeta se escapa con
`escapar-applescript`, como en el resto de rutas. Tope de correos leídos:
**[D4]**.

**Almacén.** `~/.email-triage/remitentes_importantes.json`, con este contenido:

- las direcciones normalizadas;
- su conteo;
- su origen (`archivados` o `vip`);
- `generado_en`.

No guarda asuntos. Es regenerable y se escribe con temp + `os.replace` y
permisos 700, como `calibracion.json`. Es una escritura nueva, así que hay que
añadirla al inventario de `CLAUDE.md` y al docstring de `triage_helpers.py`.
Caduca como la calibración (7 días). Es texto plano a propósito, para que el
mantenedor pueda revisarlo y borrar entradas.

**Scoring.** Si el payload trae `remitente` y la dirección está en la lista, el
resultado lleva `remitente_importante: true` y su origen, y se aplica el suelo.
La regla es la de `prioritario` y vive en un solo sitio.

**Exclusiones fijas:**

- las direcciones propias del usuario (no aprender de los correos que se
  envía a sí mismo);
- `no-reply@` / `noreply@`, salvo que el usuario las añada a mano.

## Fases (un PR cada una)

0. **Sonda en el Mac del mantenedor** (`scripts/sonda_vip.py`, solo cuenta).
   Comprobar si el diccionario AppleScript de Mail.app expone la lista de VIP,
   si hay buzones con «VIP» visibles por AppleScript, o si los datos de Mail la
   guardan en un plist legible. *No está verificado:* si ninguna vía funciona,
   se descartan los VIP y queda solo «Archivados».
1. **Leer y guardar, sin efecto.** `remitente_importante` sale en el scoring y
   en el informe como dato **informativo**, sin suelo. Permite ver en triajes
   reales cuántos correos tocaría antes de que cambie nada.
2. **Activar el suelo** (opt-in) con el tier de [D1].
3. **Ampliar «Conservar»**: leer más de 100 correos y usar todos los remitentes,
   no solo los 10 primeros, para la atenuación de la B. Sin suelo nuevo: el
   mantenedor rechazó D5.

Cada fase lleva sus tests, que fijan el comportamiento:

- sin config, todo igual;
- los asuntos nunca se guardan;
- `+sufijo` y dominios genéricos;
- inyección por encima del suelo;
- remitente suplantado.

## Decisiones del mantenedor

Respondidas el 2026-11-02: **D1, D2, D3 y D4 aceptadas tal como se proponían;
D5 rechazada.**

- **[D1]** Tier mínimo de un remitente de «Archivados»: `REVIEW` (siempre lo ves)
  o `READING_LATER` (nunca se archiva, pero no reclama atención). Propuesta:
  `REVIEW`, porque ahí están las respuestas de personas y las facturas.
- **[D2]** ¿Los VIP pesan igual que «Archivados», o más? Por ejemplo, VIP con suelo
  `REVIEW` y «Archivados» con `READING_LATER`. Propuesta: igual, para empezar
  simple.
- **[D3]** ¿Se aceptan dominios propios de una institución (`@universidad.es`)
  cuando aparezcan varias direcciones distintas de ese dominio? Propuesta: no
  automáticamente; el script los **sugiere** y el mantenedor los añade a mano a
  `remitentes_prioritarios`.
- **[D4]** ¿Cuántos correos de «Archivados» se leen? Propuesta: todos hasta 2.000,
  los más recientes primero.
- **[D5]** ¿Los remitentes de «Conservar» con 3 o más correos conservados deben
  tener suelo `READING_LATER`? Es lo más cercano a «priorízame newsletters como
  las que me gustan» sin leer contenido. Propuesta: sí, en la fase 3.
  **Rechazada:** la fase 3 solo amplía la atenuación de la B, sin suelo.
