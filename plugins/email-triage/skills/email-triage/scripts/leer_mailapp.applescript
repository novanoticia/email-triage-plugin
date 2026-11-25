-- Solo para leer_mailapp.py. Recibe argv y devuelve JSON crudo por un pipe
-- privado del subproceso. No ejecutar directamente desde el agente.
use framework "Foundation"
use scripting additions

on run argumentos
	set operacion to item 1 of argumentos
	set nombreCuenta to item 2 of argumentos
	set nombreBuzon to item 3 of argumentos
	set limiteMetadatos to (item 4 of argumentos) as integer
	set idCuentaEsperado to item 5 of argumentos
	set filas to {}
	tell application "Mail"
		set cuentaElegida to missing value
		repeat with unaCuenta in (every account)
			if my mismoNombre((name of unaCuenta) as text, nombreCuenta) then
				if cuentaElegida is not missing value then return my codificar({"cuenta_ambigua"})
				set cuentaElegida to contents of unaCuenta
			end if
		end repeat
		if cuentaElegida is missing value then return my codificar({"sin_cuenta"})
		set idCuenta to (id of cuentaElegida) as text
		if idCuentaEsperado is not "" and not my exacto(idCuenta, idCuentaEsperado) then return my codificar({"cuenta_cambiada"})
		set buzonElegido to missing value
		repeat with unBuzon in (every mailbox of cuentaElegida)
			if my mismoNombre((name of unBuzon) as text, nombreBuzon) then
				if buzonElegido is not missing value then return my codificar({"buzon_ambiguo"})
				set buzonElegido to contents of unBuzon
			end if
		end repeat
		if buzonElegido is missing value then return my codificar({"sin_buzon"})
		if operacion is "metadatos" then
			set limite to (item 6 of argumentos) as integer
			set ventana to (item 7 of argumentos) as integer
			if ventana > 0 then
				set corte to (current date) - (ventana * hours)
				set mensajes to (messages of buzonElegido whose date received > corte)
			else
				set mensajes to messages of buzonElegido
			end if
			set total to count of mensajes
			if total < limite then set limite to total
			repeat with i from 1 to limite
				set idElegido to id of (item i of mensajes)
				set end of filas to my leerRegistro(buzonElegido, idElegido, limiteMetadatos, 0)
			end repeat
		else if operacion is "cuerpos" then
			set limiteCrudo to (item 6 of argumentos) as integer
			set total to (count of argumentos) - 6
			repeat with i from 7 to (count of argumentos)
				set idElegido to (item i of argumentos) as integer
				set end of filas to my leerRegistro(buzonElegido, idElegido, limiteMetadatos, limiteCrudo)
			end repeat
		else
			return my codificar({"operacion_invalida"})
		end if
	end tell
	return my codificar({"ok", idCuenta, total, filas})
end run

on leerRegistro(buzonElegido, idElegido, limiteMetadatos, limiteCrudo)
	tell application "Mail"
		set coincidentes to (messages of buzonElegido whose id is idElegido)
		if (count of coincidentes) is not 1 then return {idElegido, "", "", "", "", "no_disponible", ""}
		set correoElegido to item 1 of coincidentes
		if (id of correoElegido) is not idElegido then return {idElegido, "", "", "", "", "no_disponible", ""}
		set inicioMid to my identificador(correoElegido)
		set remitente to ""
		set asunto to ""
		set fecha to ""
		try
			set remitente to my acotar((sender of correoElegido) as text, limiteMetadatos)
		end try
		try
			set asunto to my acotar((subject of correoElegido) as text, limiteMetadatos)
		end try
		try
			set fecha to (date received of correoElegido) as text
		end try
		set acceso to "metadatos"
		set cuerpo to ""
		if limiteCrudo > 0 then
			set acceso to "sin_cuerpo"
			try
				set textoCuerpo to content of correoElegido
				if textoCuerpo is not missing value then
					set cuerpo to my acotar(textoCuerpo as text, limiteCrudo)
					set acceso to "cuerpo"
				end if
			end try
		end if
		set finMid to my identificador(correoElegido)
		if (id of correoElegido) is not idElegido or not my exacto(inicioMid, finMid) then return {idElegido, "", "", "", "", "no_disponible", ""}
		return {idElegido, inicioMid, remitente, asunto, fecha, acceso, cuerpo}
	end tell
end leerRegistro

on identificador(correoElegido)
	tell application "Mail"
		try
			set mid to message id of correoElegido
			if mid is not missing value and (length of mid) ≤ 998 then return mid as text
		end try
		return ""
	end tell
end identificador

on acotar(valor, limite)
	if (length of valor) > limite then return text 1 thru limite of valor
	return valor
end acotar

on exacto(izquierda, derecha)
	set texto to current application's NSString's stringWithString:izquierda
	return (texto's isEqualToString:derecha) as boolean
end exacto

-- v3.28.9 (prueba real 2026-11-23): Mail guardaba «Leer Después» con la
-- tilde descompuesta (NFD) y el config la trae compuesta (NFC); `exacto` las
-- veía distintas y el lector devolvía sin_buzon. Los nombres de cuenta y de
-- buzón se comparan en NFC por los dos lados: equivalencia canónica, el mismo
-- texto. No ignora mayúsculas, espacios ni nada más; dos buzones que solo
-- difieran en la forma de la tilde dan buzon_ambiguo. Los identificadores
-- (cuenta, message-id) siguen con `exacto`.
on mismoNombre(izquierda, derecha)
	set nfcIzquierda to (current application's NSString's stringWithString:izquierda)'s precomposedStringWithCanonicalMapping()
	set nfcDerecha to (current application's NSString's stringWithString:derecha)'s precomposedStringWithCanonicalMapping()
	return (nfcIzquierda's isEqualToString:nfcDerecha) as boolean
end mismoNombre

on codificar(valor)
	set datos to current application's NSJSONSerialization's dataWithJSONObject:valor options:0 |error|:(missing value)
	return ((current application's NSString's alloc()'s initWithData:datos encoding:(current application's NSUTF8StringEncoding)) as text)
end codificar
