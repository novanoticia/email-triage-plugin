#!/usr/bin/env python3
"""Mide por qué las filas de `hibrido` vuelven al principal (evaluadores LLM).

Herramienta de desarrollo (no se distribuye con el plugin). Envía 40 correos
INVENTADOS (nunca reales) al proveedor elegido en modo `hibrido`, con el
config plantilla del repo, y cuenta los motivos por fila, los criterios en
`__no_aplica__` y los tiers de las propuestas. Por correo muestra solo lo que
con correos inventados no expone nada: las dudas, los criterios con evidencia
vacía y, si el eco falla, el eco esperado frente al recibido.

No toca ~/.email-triage, no lee el buzón, no mueve nada y no muestra la
clave. Uso, desde la raíz del repositorio (resultados en
docs/mediciones-evaluadores.md):

    PROVEEDOR=gemini python3 scripts/medir_evaluadores.py
    PROVEEDOR=apple PAUSA=0 python3 scripts/medir_evaluadores.py  # con fm serve
    PROVEEDOR=ollama PAUSA=0 python3 scripts/medir_evaluadores.py  # ~75 min

PAUSA (segundos entre llamadas, 4.5 por defecto) evita el límite por minuto
del nivel gratuito de Gemini.
"""
import collections
import os
import sys

PROVEEDOR = os.environ.get("PROVEEDOR", "gemini")

sys.path.insert(0, "plugins/email-triage/skills/email-triage/scripts")
import yaml  # noqa: E402
import evaluadores as ev  # noqa: E402
import triage_helpers as th  # noqa: E402

PERFIL = ("Coordino una asociación cultural ficticia: talleres, socios, "
          "subvenciones y voluntariado. Mi tiempo es limitado.")
CORREOS = [  # (asunto, remitente, cuerpo): todos inventados
    ("Boletín de noviembre", "boletin@example.invalid", "Novedades del mes: diez artículos sobre jardinería urbana y una receta de otoño."),
    ("Factura 2026-118", "facturacion@example.invalid", "Adjuntamos la factura del alquiler de la sala de octubre. Vence el día 15."),
    ("¿Podemos vernos el jueves?", "lucia@example.invalid", "Hola, necesito que decidamos antes del viernes si renovamos el convenio con el ayuntamiento. ¿Te va el jueves a las 18?"),
    ("¡Oferta exclusiva solo hoy!", "promo@example.invalid", "Descuento del 70 % en cursos online. Pulsa aquí antes de medianoche."),
    ("Tu contraseña se ha cambiado", "no-responder@example.invalid", "Se ha cambiado la contraseña de tu cuenta. Si no fuiste tú, contacta con soporte."),
    ("Encuesta de satisfacción", "encuestas@example.invalid", "Valora tu experiencia con nuestro servicio en dos minutos."),
    ("Convocatoria de subvenciones 2027", "cultura@example.invalid", "Se abre el plazo para proyectos culturales: hasta 12.000 euros. Solicitudes hasta el 30 de noviembre."),
    ("Duda sobre el taller de cerámica", "socio42@example.invalid", "Me apunté al taller del sábado, pero no sé si tengo que llevar material propio."),
    ("Recordatorio: asamblea anual", "secretaria@example.invalid", "La asamblea es el 20 de noviembre. Hay que votar el presupuesto; envía tu delegación si no puedes venir."),
    ("Artículo que te puede interesar", "amigo@example.invalid", "Leí este ensayo sobre gestión del voluntariado y me acordé de vuestra asociación."),
    ("Error en la web", "voluntario@example.invalid", "El formulario de inscripción da error al enviar. Varios socios no pueden apuntarse al taller."),
    ("Notificación de envío", "logistica@example.invalid", "Tu pedido de pinturas ha salido del almacén y llegará en tres días."),
    ("Propuesta de colaboración", "galeria@example.invalid", "Somos una galería del barrio y nos gustaría organizar con vosotros una exposición conjunta en primavera. ¿Lo hablamos?"),
    ("Baja de socio", "socio17@example.invalid", "Por motivos personales quiero darme de baja de la asociación a final de año. ¿Qué tengo que hacer?"),
    ("Cambio de horario del local", "propietario@example.invalid", "A partir de diciembre el local cerrará a las 21:00 en lugar de a las 22:00 por obras en el edificio."),
    ("Webinar gratuito: marketing para ONG", "eventos@example.invalid", "Únete a nuestro webinar sobre captación de socios. Plazas limitadas."),
    ("Presupuesto de imprenta", "imprenta@example.invalid", "Os enviamos el presupuesto de 500 carteles: 180 euros. Si lo aceptáis antes del lunes, lo tenemos en una semana."),
    ("Queja sobre el ruido", "vecina@example.invalid", "Los ensayos del martes terminan muy tarde y se oyen en todo el edificio. Os pido que lo tengáis en cuenta."),
    ("Resumen semanal de tu cuenta", "estadisticas@example.invalid", "Esta semana tu página tuvo 120 visitas, un 5 % más que la anterior."),
    ("Necesito el certificado de voluntariado", "estudiante@example.invalid", "Para mi universidad necesito un certificado de las horas que hice el verano pasado. ¿Me lo podéis enviar antes del día 10?"),
    ("Nuevo reglamento de protección de datos", "gestoria@example.invalid", "Os recordamos que antes de enero debéis actualizar el registro de actividades de tratamiento de datos de socios."),
    ("Foto del taller", "socia8@example.invalid", "Os paso la foto que hicimos el sábado. ¡Qué bien salió!"),
    ("Has ganado un premio", "premios@example.invalid", "Enhorabuena, has sido seleccionado para recibir un premio. Confirma tus datos bancarios para recibirlo."),
    ("Renovación del seguro", "seguros@example.invalid", "La póliza de responsabilidad civil vence el 31 de diciembre. Si no indicáis lo contrario, se renovará con una subida del 8 %."),
    ("Ideas para la fiesta de invierno", "comision@example.invalid", "Hemos pensado tres opciones para la fiesta: cena, concierto o mercadillo. Necesitamos que elijas una antes del miércoles."),
    ("Actualización de la app", "app@example.invalid", "Hemos mejorado el rendimiento y corregido errores menores. No tienes que hacer nada."),
    ("Préstamo de proyector", "otra-asociacion@example.invalid", "¿Nos podríais prestar el proyector el sábado 16? Lo devolvemos el lunes."),
    ("Recordatorio de cuota", "tesoreria@example.invalid", "Faltan 14 socios por pagar la cuota anual. ¿Mando un recordatorio general o les escribo uno a uno?"),
    ("Newsletter de cultura", "revista@example.invalid", "Entrevista a una ceramista, agenda de exposiciones y una reseña de teatro."),
    ("Solicitud de entrevista para la radio", "radio@example.invalid", "Queremos entrevistaros en el programa local sobre el taller de cerámica. ¿Os va el jueves 21 por la mañana?"),
    ("Factura duplicada", "proveedor@example.invalid", "Hemos detectado que os enviamos dos veces la factura 77. Ignorad la segunda, por favor."),
    ("Invitación a inauguración", "museo@example.invalid", "Os invitamos a la inauguración de la nueva sala el viernes a las 19:00."),
    ("Problema con el pago", "banco@example.invalid", "El cargo de la cuota del socio 23 ha sido devuelto. Puedes revisarlo en tu banca online."),
    ("Voluntarios para la feria", "feria@example.invalid", "Buscamos dos voluntarios de vuestra asociación para el stand del domingo. ¿Contamos con vosotros?"),
    ("Encuesta del ayuntamiento", "participacion@example.invalid", "El ayuntamiento abre una consulta sobre el uso de los centros cívicos. Plazo: 30 de noviembre."),
    ("Material olvidado", "conserje@example.invalid", "Alguien se dejó una caja de pinceles en la sala 2. La guardo en conserjería."),
    ("Oferta de hosting", "hosting@example.invalid", "Migra tu web a nuestro servicio y ahorra un 40 % el primer año."),
    ("Conflicto entre voluntarios", "coordinadora@example.invalid", "Dos voluntarios del taller de los jueves no se entienden y uno amenaza con dejarlo. Creo que deberíamos hablarlo esta semana."),
    ("Confirmación de reserva", "reservas@example.invalid", "Tu reserva de la sala grande para el 12 de diciembre está confirmada."),
    ("Pregunta sobre accesibilidad", "familia@example.invalid", "Mi hijo usa silla de ruedas. ¿El local tiene acceso adaptado para el taller infantil?"),
]

cfg = yaml.safe_load(open("plugins/email-triage/skills/email-triage/config.yaml", encoding="utf-8"))
p = ev.preparar({"perfil_minimo": PERFIL, "emails": [
    {"id": str(i + 1), "asunto": a, "remitente": r, "cuerpo": c}
    for i, (a, r, c) in enumerate(CORREOS)]})
for e in p["emails"]:
    e["control"] = {"hard_rules": [], "extra_points": 0, "forzar_reply_needed": False,
                    "tier_maximo": None, "remitente_en_historial": False}
    e["contexto_suficiente"] = True

capa = {"activo": True, "acepta_envio_datos": True, "modo": "hibrido",
        "proveedor": PROVEEDOR, "max_llamadas": len(CORREOS),
        # Ollama tarda unos 110 s por correo en un Mac de 16 GB (tope 600).
        "timeout_segundos": int(os.environ.get("TIMEOUT", "300" if PROVEEDOR == "ollama" else "60"))}
prov = ev.proveedor(PROVEEDOR)
crudas = {}  # id -> respuesta estructurada tal como llegó (antes de validarla)


import time  # noqa: E402
PAUSA = float(os.environ.get("PAUSA", "4.5"))  # nivel gratuito: ~15 llamadas/minuto


def capturar(body, key, timeout):
    if crudas or capturar.llamadas:
        time.sleep(PAUSA)
    capturar.llamadas += 1
    respuesta = prov.solicitar(body, key, timeout)
    try:
        contenido = prov.extraer(respuesta)
        for fila in contenido.get("evaluaciones", []):
            crudas[str(fila.get("id"))] = fila
    except Exception:
        pass  # la validación real la hace evaluadores.py
    return respuesta


capturar.llamadas = 0
print("Enviando %d correos inventados a %s (unos %d s)..." % (len(CORREOS), PROVEEDOR, int(len(CORREOS) * PAUSA)))
r = ev.evaluar(p, cfg, capa, capturar)

motivos = collections.Counter(f.get("motivo") for f in r["resultados"])
no_aplica = collections.Counter()
con_dudas = 0
tiers = collections.Counter()
for f in r["resultados"]:
    # Desde la respuesta capturada ANTES de validarla: `evaluacion_<proveedor>`
    # solo existe si la fila pasa el eco y la validación, y contar desde ahí
    # ocultaría las dudas y exclusiones de las filas rechazadas.
    crit = (crudas.get(f["id"]) or {}).get("criterios") or {}
    no_aplica.update(k for k, c in crit.items()
                     if isinstance(c, dict) and c.get("veredicto") == "__no_aplica__")
    con_dudas += bool((crudas.get(f["id"]) or {}).get("dudas"))
    if f.get("propuesta"):
        tiers[f["propuesta"]["tier"]] += 1

print("proveedor:", PROVEEDOR, "| ok:", r.get("ok"), "| motivo general:", r.get("motivo", "-"),
      "| llamadas:", r.get("llamadas"), "| coste USD:", r["consumo"].get("coste_estimado_usd"))
print("cobertura:", r.get("cobertura"))
print("motivos por fila:")
for m, n in motivos.most_common():
    print("   %-36s %d" % (m, n))
print("filas con dudas anotadas (también las rechazadas):", con_dudas, "de", len(CORREOS))
print("propuestas (validadas + a reevaluar):", sum("propuesta" in f for f in r["resultados"]), "de", len(CORREOS))
print("criterios en __no_aplica__ (veces, también en filas rechazadas):", dict(no_aplica.most_common()))
print("tiers de las propuestas que quedan:", dict(tiers))

print()
print("=== detalle por correo (inventados) ===")
asuntos = {str(i + 1): a for i, (a, _, _) in enumerate(CORREOS)}
for f in r["resultados"]:
    fila = crudas.get(f["id"], {})
    crit = fila.get("criterios") or {}
    vacias = sorted(k for k, c in crit.items() if isinstance(c, dict)
                    and c.get("veredicto") != "__no_aplica__"
                    and not str(c.get("evidencia", "")).strip())
    print("[%s] %s -> %s" % (f["id"], asuntos.get(f["id"]), f.get("motivo")))
    for d in fila.get("dudas") or []:
        print("     duda:", str(d)[:220])
    if vacias:
        print("     evidencia vacía en:", ", ".join(vacias))
    if f.get("motivo") == "eco_distinto":
        texto = next(x["estado"]["texto"] for x in p["emails"] if x["id"] == f["id"])
        print("     eco esperado:", th.ancla_extracto(texto))
        print("     eco recibido:", fila.get("eco"))
