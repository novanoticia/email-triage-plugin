"""Perfil y 40 correos INVENTADOS para las mediciones de desarrollo.

Compartidos por `medir_evaluadores.py` y `sonda_decision_local.py` para que
las mediciones de todos los proveedores usen exactamente los mismos correos.
Ninguno es real; no se distribuyen con el plugin.

`ESPERADOS` (2026-11-01, aceptado por el mantenedor) da, por correo y en el
mismo orden, el tier que debería salir y los controles que pondría el
principal: P pregunta directa, D plazo explícito, B remitente masivo y F
forzar `REPLY_NEEDED`. Sin F, el scoring capa `REPLY_NEEDED` a `REVIEW`
(`cap_reply_needed_sin_accion`): por eso las mediciones 1-12, que enviaban
controles vacíos, no podían dar ningún `REPLY_NEEDED`.
"""
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

# (tier esperado, controles): mismo orden que CORREOS.
ESPERADOS = [
    ("ARCHIVE", "B"),            # 1 boletín ajeno al perfil
    ("REVIEW", "D"),             # 2 factura: pagar, no responder
    ("REPLY_NEEDED", "PDF"),     # 3 decidir antes del viernes
    ("ARCHIVE", "B"),            # 4 promoción
    ("REVIEW", "B"),             # 5 contraseña: solo si no fuiste tú
    ("ARCHIVE", "B"),            # 6 encuesta ritual
    ("REVIEW", "D"),             # 7 subvención, plazo lejano
    ("REPLY_NEEDED", "PF"),      # 8 un socio espera respuesta
    ("REVIEW", "D"),             # 9 asamblea: votar o delegar
    ("READING_LATER", ""),       # 10 artículo de un amigo
    ("REPLY_NEEDED", "F"),       # 11 la web bloquea a socios
    ("ARCHIVE", "B"),            # 12 envío informativo
    ("REPLY_NEEDED", "PF"),      # 13 colaboración: pregunta directa
    ("REPLY_NEEDED", "PF"),      # 14 baja: «¿qué tengo que hacer?»
    ("REVIEW", ""),              # 15 horario del local
    ("ARCHIVE", "B"),            # 16 webinar promocional
    ("REPLY_NEEDED", "DF"),      # 17 aceptar antes del lunes
    ("REVIEW", ""),              # 18 queja sin pregunta
    ("ARCHIVE", "B"),            # 19 métrica sin acción
    ("REPLY_NEEDED", "PDF"),     # 20 certificado antes del día 10
    ("REVIEW", "D"),             # 21 obligación legal
    ("READING_LATER", ""),       # 22 foto del taller
    ("ARCHIVE", "B"),            # 23 phishing
    ("REVIEW", "D"),             # 24 seguro con subida
    ("REPLY_NEEDED", "PDF"),     # 25 elegir antes del miércoles
    ("ARCHIVE", "B"),            # 26 «no tienes que hacer nada»
    ("REPLY_NEEDED", "PF"),      # 27 préstamo para el sábado
    ("REPLY_NEEDED", "PF"),      # 28 piden que decidas
    ("READING_LATER", "B"),      # 29 newsletter afín
    ("REPLY_NEEDED", "PF"),      # 30 entrevista con fecha
    ("ARCHIVE", ""),             # 31 «ignorad la segunda»
    ("READING_LATER", ""),       # 32 inauguración opcional
    ("REVIEW", ""),              # 33 cuota devuelta
    ("REPLY_NEEDED", "PF"),      # 34 «¿contamos con vosotros?»
    ("REVIEW", "D"),             # 35 consulta municipal
    ("ARCHIVE", ""),             # 36 material ajeno
    ("ARCHIVE", "B"),            # 37 promoción
    ("REPLY_NEEDED", "F"),       # 38 hablarlo esta semana
    ("ARCHIVE", ""),             # 39 solo confirma
    ("REPLY_NEEDED", "PF"),      # 40 pregunta directa de una familia
]
REGLAS = {"P": "pregunta_directa_boost", "D": "deadline_explicito_boost",
          "B": "sender_bulk_penalizacion"}


def control(letras):
    """Control del principal para `letras` de ESPERADOS (o vacío con "")."""
    return {"hard_rules": [REGLAS[x] for x in letras if x in REGLAS],
            "extra_points": 0, "forzar_reply_needed": "F" in letras,
            "tier_maximo": None, "remitente_en_historial": False}
