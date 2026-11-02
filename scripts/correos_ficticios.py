"""Perfil y 80 correos INVENTADOS para las mediciones de desarrollo.

Compartidos por `medir_evaluadores.py` y `sonda_decision_local.py` para que
las mediciones de todos los proveedores usen exactamente los mismos correos.
Ninguno es real; no se distribuyen con el plugin.

`ESPERADOS` (2026-11-01, aceptado por el mantenedor) da, por correo y en el
mismo orden, el tier que debería salir y los controles que pondría el
principal: P pregunta directa, D plazo explícito, B remitente masivo y F
forzar `REPLY_NEEDED`. Sin F, el scoring capa `REPLY_NEEDED` a `REVIEW`
(`cap_reply_needed_sin_accion`): por eso las mediciones 1-12, que enviaban
controles vacíos, no podían dar ningún `REPLY_NEEDED`.

Desde el 2026-11-02 (decisión del mantenedor) los correos sociales sin nada
que hacer (22 y 60-63: foto, agradecimiento, felicitación, crónica, saludo)
esperan `ARCHIVE`, no `READING_LATER`: con la pregunta del plugin («¿leer esto
cambiaría algo?») no cambian ninguna decisión. Las mediciones 1-18 se hicieron
con la expectativa anterior.
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
    # 41-80 (2026-11-02, medición 18): más largos que los 40 primeros, que
    # eran de una línea, y cargados hacia los casos dudosos de las
    # mediciones 15-17: avisos que confirman lo esperado frente a avisos que
    # piden algo, boletines afines y ajenos, invitaciones y correos sociales.
    ("Inscripción confirmada", "inscripciones@example.invalid", "Hemos recibido tu inscripción en la Feria de Asociaciones del 14 de marzo. Tu stand es el número 23, como solicitaste. No tienes que hacer nada más: te enviaremos el plano unos días antes."),
    ("Recibo cobrado", "banco@example.invalid", "Te informamos de que se ha cargado en tu cuenta el recibo de la cuota mensual de la sala, por el importe habitual de 85 euros. Puedes consultar el detalle en la banca online."),
    ("Pedido entregado", "logistica@example.invalid", "Tu pedido de cartulinas y rotuladores se entregó ayer a las 12:40 en la dirección indicada. Lo recogió la persona de conserjería. Gracias por tu compra."),
    ("Hemos recibido tu solicitud", "registro@example.invalid", "Confirmamos la recepción de vuestra solicitud de subvención para el ciclo de talleres de 2027, con número de registro 4471. La resolución se publicará en el plazo previsto en las bases. No es necesario responder a este mensaje."),
    ("Copia de seguridad completada", "avisos@example.invalid", "La copia de seguridad semanal de vuestra web se completó correctamente el domingo a las 03:00. Tamaño: 1,2 GB. La próxima copia se hará automáticamente dentro de siete días."),
    ("Tu dominio se ha renovado", "dominios@example.invalid", "El dominio de vuestra asociación se ha renovado automáticamente por un año, al mismo precio que el anterior. El cargo aparecerá en la tarjeta que tienes registrada."),
    ("Pago rechazado", "suministros@example.invalid", "El recibo de la luz del local de octubre ha sido devuelto por el banco. Para evitar recargos, abonadlo en los próximos cinco días por transferencia; si no, se aplicará un recargo del 10 %."),
    ("Tu dominio caduca en 7 días", "dominios@example.invalid", "No hemos podido renovar el dominio de vuestra asociación porque la tarjeta registrada ha caducado. Si no actualizas el medio de pago antes del día 9, la web y el correo dejarán de funcionar."),
    ("Inicio de sesión desde un dispositivo nuevo", "seguridad@example.invalid", "Se ha iniciado sesión en la cuenta de la asociación desde un ordenador nuevo, en otra ciudad, hoy a las 04:12. Si has sido tú, puedes ignorar este mensaje; si no, cambia la contraseña cuanto antes."),
    ("Cambio en tu entrega", "logistica@example.invalid", "Por una incidencia en el almacén, tu pedido de arcilla para el taller no llegará el viernes, sino el martes siguiente. Disculpa las molestias."),
    ("Boletín de la red de asociaciones culturales", "red@example.invalid", "Este mes: cómo organizó una asociación de otra ciudad su primera campaña de financiación colectiva, con cifras y errores incluidos; una entrevista sobre voluntariado joven, y la agenda de encuentros de primavera."),
    ("Novedades de la biblioteca municipal", "biblioteca@example.invalid", "En diciembre empieza un club de lectura sobre novela gráfica y un ciclo de cine documental los jueves. También hemos ampliado el fondo de libros sobre artesanía y cerámica."),
    ("Lo mejor del mes en gestión cultural", "blog@example.invalid", "Tres artículos para leer con calma: cómo escribir una memoria de actividades que convenza, qué aprendimos de un año de talleres gratuitos y una guía breve para coordinar voluntarios sin quemarse."),
    ("Novedades en electrónica", "tienda@example.invalid", "Descubre los nuevos auriculares inalámbricos, las ofertas en televisores y nuestra selección de regalos tecnológicos para estas fiestas. Envío gratis en pedidos superiores a 50 euros."),
    ("Pisos en tu zona", "inmobiliaria@example.invalid", "Esta semana hemos incorporado doce viviendas nuevas cerca de ti. Consulta precios, fotos y planos en nuestra web y pide visita sin compromiso."),
    ("Presentación del libro de Marta", "marta@example.invalid", "Como sabéis, por fin he publicado el libro de relatos que empecé en el taller de escritura. Lo presento el sábado 30 en la librería de la plaza a las 19:00. Me haría mucha ilusión veros, pero sin ningún compromiso."),
    ("Jornada de asociaciones del distrito", "participacion@example.invalid", "El distrito organiza una jornada para que las asociaciones presenten sus proyectos a los vecinos el 18 de enero. Las que quieran mesa propia deben inscribirse antes del 20 de diciembre en el formulario de la web municipal."),
    ("Invitación: Feria Internacional del Regalo", "feria-comercial@example.invalid", "Le invitamos a visitar la mayor feria del sector del regalo y la decoración, con más de 600 expositores. Registre su pase profesional gratuito antes del 15 de enero."),
    ("Concierto del coro del barrio", "coro@example.invalid", "El coro con el que compartimos local da un concierto de villancicos el día 21 en la iglesia de la esquina. Entrada libre. Os esperamos si os apetece."),
    ("Gracias por el taller infantil", "familia2@example.invalid", "Solo quería deciros que mi hija volvió encantada del taller de máscaras del sábado. Lleva toda la semana enseñándosela a todo el mundo. Gracias por el cariño con el que lo preparáis."),
    ("¡Feliz cumpleaños!", "socio23@example.invalid", "Me he enterado de que hoy es tu cumpleaños. Muchas felicidades de parte de todo el grupo de los martes. ¡Que lo celebres a lo grande!"),
    ("Crónica del mercadillo", "voluntario3@example.invalid", "Os paso unas líneas y unas fotos del mercadillo solidario del domingo. Vino mucha gente del barrio, se vendió casi toda la cerámica y los niños se lo pasaron en grande con el taller de chapas."),
    ("Saludos desde Galicia", "antigua-socia@example.invalid", "Hace ya un año que me mudé y todavía echo de menos los jueves de cerámica. Aquí he encontrado un grupo parecido, pero no es lo mismo. Un abrazo fuerte a todos."),
    ("Cambio en el IVA de las actividades", "gestoria@example.invalid", "A partir del 1 de enero cambia el tipo de IVA aplicable a algunas actividades formativas de las asociaciones. Revisad si vuestros talleres de pago están afectados antes de fijar los precios de 2027."),
    ("Resolución provisional de subvenciones", "cultura@example.invalid", "Se ha publicado la resolución provisional: vuestro proyecto queda en lista de espera, en el puesto 3. Hay diez días hábiles para presentar alegaciones o reformular el presupuesto."),
    ("Balance del trimestre", "tesorera@example.invalid", "Te adjunto el balance del tercer trimestre. Cuadra todo salvo una diferencia de 300 euros entre la caja y el banco que no consigo localizar. Habría que revisarlo antes de la asamblea."),
    ("Corte de agua el jueves", "propietario@example.invalid", "La comunidad nos avisa de que el jueves 12 no habrá agua en el edificio de 9:00 a 15:00 por una reparación. Lo digo por si afecta al taller de cerámica de la mañana."),
    ("Taller de enero", "profesora@example.invalid", "Necesito saber si mantenemos el taller de acuarela en enero o lo aplazamos a febrero, porque tengo que organizar mi calendario. ¿Me lo confirmas antes del día 15?"),
    ("Declaraciones para la radio local", "periodista@example.invalid", "Estoy preparando una pieza sobre el mercadillo solidario para el informativo de mañana. ¿Podrías darme dos o tres frases antes de las 12:00?"),
    ("¿Puedo traer a mi hijo?", "socio31@example.invalid", "Me gustaría venir al taller de encuadernación del sábado, pero no tengo con quién dejar a mi hijo de 9 años. ¿Puedo traerlo si se queda tranquilo leyendo?"),
    ("Entrega de las sillas", "mobiliario@example.invalid", "Tenemos listas las 30 sillas plegables que encargasteis. ¿Nos confirmáis la dirección de entrega y si hay alguien en el local por las mañanas?"),
    ("Cambio de turno", "voluntaria5@example.invalid", "Este sábado me ha surgido un compromiso familiar. ¿Podría cambiar mi turno de la mañana por el de la tarde, o buscamos a otra persona?"),
    ("Documentación pendiente", "registro@example.invalid", "Para tramitar vuestra solicitud falta el certificado de estar al corriente con Hacienda. Tenéis diez días hábiles para aportarlo. ¿Podéis enviarlo por la sede electrónica?"),
    ("Su cuenta será suspendida", "verificacion@example.invalid", "Hemos detectado actividad inusual. Para evitar la suspensión de su cuenta en 24 horas, verifique sus datos y su tarjeta en el enlace adjunto."),
    ("Seguro de hogar al mejor precio", "ofertas@example.invalid", "Compara y ahorra hasta un 30 % en tu seguro de hogar. Calcula tu precio en dos minutos y llévate un regalo al contratar."),
    ("¿Qué opinas de nuestro software?", "encuestas@example.invalid", "Como usuario de nuestra plataforma de facturación, tu opinión nos importa. Responde a esta encuesta de diez preguntas y participa en el sorteo de una tarjeta regalo."),
    ("A 3 personas les gusta tu publicación", "notificaciones@example.invalid", "A Ana, Luis y una persona más les gusta la publicación de vuestra página sobre el mercadillo. Mira quién más ha interactuado esta semana."),
    ("Re: Acta de la reunión", "secretaria@example.invalid", "Perfecto, así queda aprobada. Gracias a todos."),
    ("Por si os interesa este curso", "socio12@example.invalid", "Me ha llegado esta información de un curso gratuito sobre restauración de muebles en el centro cívico. Yo no puedo ir, pero pensé que a alguien del grupo le podría gustar."),
    ("Una idea para el año que viene", "socio40@example.invalid", "Llevo tiempo pensando que podríamos abrir un taller de reparación de bicis con los jóvenes del barrio. Tengo herramientas y conozco a dos mecánicos dispuestos a echar una mano. Os lo cuento para que lo pensemos en la próxima reunión."),
]

# (tier esperado, controles): mismo orden que CORREOS.
ESPERADOS = [
    ("ARCHIVE", "B"),            # 1 boletín ajeno al perfil
    ("REVIEW", "D"),             # 2 factura: pagar, no responder
    ("REPLY_NEEDED", "PDF"),     # 3 decidir antes del viernes
    ("ARCHIVE", "B"),            # 4 promoción
    ("REVIEW", ""),              # 5 aviso de seguridad: sin B (medición 13)
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
    ("ARCHIVE", ""),             # 22 foto del taller (social, 2026-11-02)
    ("ARCHIVE", "B"),            # 23 phishing
    ("REVIEW", "D"),             # 24 seguro con subida
    ("REPLY_NEEDED", "PDF"),     # 25 elegir antes del miércoles
    ("ARCHIVE", "B"),            # 26 «no tienes que hacer nada»
    ("REPLY_NEEDED", "PF"),      # 27 préstamo para el sábado
    ("REPLY_NEEDED", "PF"),      # 28 piden que decidas
    ("READING_LATER", "B"),      # 29 newsletter afín
    ("REPLY_NEEDED", "PF"),      # 30 entrevista con fecha
    ("REVIEW", ""),              # 31 «ignorad la segunda»: pide no pagar dos veces (mantenedor, medición 15)
    ("READING_LATER", ""),       # 32 inauguración opcional
    ("REVIEW", ""),              # 33 cuota devuelta
    ("REPLY_NEEDED", "PF"),      # 34 «¿contamos con vosotros?»
    ("REVIEW", "D"),             # 35 consulta municipal
    ("ARCHIVE", ""),             # 36 material ajeno
    ("ARCHIVE", "B"),            # 37 promoción
    ("REPLY_NEEDED", "F"),       # 38 hablarlo esta semana
    ("ARCHIVE", ""),             # 39 solo confirma
    ("REPLY_NEEDED", "PF"),      # 40 pregunta directa de una familia
    # 41-80 (borrador 2026-11-02, pendiente de que lo acepte el mantenedor).
    ("ARCHIVE", "B"),            # 41 confirma lo que ya pediste
    ("ARCHIVE", "B"),            # 42 cargo habitual, sin cambios
    ("ARCHIVE", "B"),            # 43 entrega ya hecha
    ("ARCHIVE", "B"),            # 44 acuse de recibo sin acción
    ("ARCHIVE", "B"),            # 45 copia de seguridad correcta
    ("ARCHIVE", "B"),            # 46 renovación automática, mismo precio
    ("REVIEW", "D"),             # 47 recibo devuelto: pagar en 5 días
    ("REVIEW", "D"),             # 48 tarjeta caducada: el dominio cae el día 9
    ("REVIEW", ""),              # 49 inicio de sesión raro (como el 5)
    ("REVIEW", ""),              # 50 la arcilla no llega al taller
    ("READING_LATER", "B"),      # 51 boletín afín con un caso útil
    ("READING_LATER", "B"),      # 52 biblioteca: actividades afines
    ("READING_LATER", "B"),      # 53 blog afín, para leer con calma
    ("ARCHIVE", "B"),            # 54 tienda ajena al perfil
    ("ARCHIVE", "B"),            # 55 inmobiliaria ajena
    ("READING_LATER", ""),       # 56 presentación de una socia, sin compromiso
    ("REVIEW", "D"),             # 57 jornada: inscribirse antes del 20
    ("ARCHIVE", "B"),            # 58 feria comercial masiva
    ("READING_LATER", ""),       # 59 concierto de vecinos, entrada libre
    ("ARCHIVE", ""),             # 60 agradecimiento de una familia (social, 2026-11-02)
    ("ARCHIVE", ""),             # 61 felicitación de cumpleaños (social, 2026-11-02)
    ("ARCHIVE", ""),             # 62 crónica del mercadillo (social, 2026-11-02)
    ("ARCHIVE", ""),             # 63 saludo de una antigua socia (social, 2026-11-02)
    ("REVIEW", "D"),             # 64 cambio de IVA antes de fijar precios
    ("REVIEW", "D"),             # 65 alegaciones en diez días
    ("REVIEW", ""),              # 66 descuadre de 300 euros
    ("REVIEW", "D"),             # 67 sin agua el jueves del taller
    ("REPLY_NEEDED", "PDF"),     # 68 confirmar el taller antes del 15
    ("REPLY_NEEDED", "PDF"),     # 69 declaraciones antes de las 12
    ("REPLY_NEEDED", "PF"),      # 70 «¿puedo traerlo?»
    ("REPLY_NEEDED", "PF"),      # 71 confirmar la dirección
    ("REPLY_NEEDED", "PF"),      # 72 cambio de turno
    ("REPLY_NEEDED", "PDF"),     # 73 documentación en diez días
    ("ARCHIVE", "B"),            # 74 phishing
    ("ARCHIVE", "B"),            # 75 seguro genérico
    ("ARCHIVE", "B"),            # 76 encuesta de un proveedor
    ("ARCHIVE", "B"),            # 77 notificación de red social
    ("ARCHIVE", ""),             # 78 cierre de hilo: «gracias a todos»
    ("READING_LATER", ""),       # 79 curso reenviado por un socio
    ("REVIEW", ""),              # 80 propuesta para la próxima reunión
]
REGLAS = {"P": "pregunta_directa_boost", "D": "deadline_explicito_boost",
          "B": "sender_bulk_penalizacion"}


def control(letras):
    """Control del principal para `letras` de ESPERADOS (o vacío con "")."""
    return {"hard_rules": [REGLAS[x] for x in letras if x in REGLAS],
            "extra_points": 0, "forzar_reply_needed": "F" in letras,
            "tier_maximo": None, "remitente_en_historial": False}
