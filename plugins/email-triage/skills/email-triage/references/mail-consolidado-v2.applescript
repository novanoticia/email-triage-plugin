-- ════════════════════════════════════════════════════════════════
-- mail-consolidado v2 — lectura en DOS pasadas (metadatos + cuerpos)
-- Motivo (probado en ejecución real, 2026-07-21):
--   El SCRIPT 1 v1 devolvía los metadatos SOLO al final, tras volcar
--   los 50 cuerpos. Con Mail a ~2-3 s/correo eso son >2 min en una
--   sola llamada; cualquier timeout del conector se come TODA la
--   salida aunque los cuerpos ya estén en disco. Y como los cuerpos
--   se indexaban por posición de carpeta (tbody_i == item i of msgs),
--   si entraba correo nuevo a mitad de sesión tbody_i dejaba de
--   corresponder al mensaje i, sin ningún error visible.
--
-- Fix:
--   · SCRIPT 1A: SOLO metadatos (sin `content of m`) → retorna en
--     segundos, sirve de índice estable (idx, fecha, remitente,
--     asunto, message-id).
--   · SCRIPT 1B: cuerpos localizados POR message-id (`whose`), y el
--     fichero se indexa por POSICIÓN EN LA LISTA que pasa el
--     orquestador (no por posición de carpeta). Robusto a reordenación
--     y reanudable (el orquestador pasa solo los mids pendientes).
--
-- REGLA DE ESCAPADO (igual que v1): pasa CUENTA/ORIGEN por
-- `escapar-applescript` (campo `escapados`) y la lista de message-ids
-- por el campo `lista_applescript` del helper. Nunca pegues valores
-- crudos entre comillas. Ejecuta escribiendo a fichero y
-- `osascript /ruta/x.scpt` (los acentos rompen el inline).
-- Placeholders: <<CUENTA>>, <<ORIGEN>>, <<LIMITE>>, <<LISTA_MIDS>>
-- ════════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────────────
-- SCRIPT 1A — METADATOS PRIMERO (rápido, sin cuerpos)
-- Devuelve TOTAL + una fila por correo. Sin `content of m`, así que
-- no paga el coste caro de extracción: retorna en segundos, no minutos.
-- El orquestador guarda estas filas y construye con ellas la lista de
-- message-ids que pasará a 1B.
-- ───────────────────────────────────────────────────────────────
tell application "Mail"
	set acct to account "<<CUENTA>>"
	set srcBox to missing value
	repeat with mb in (every mailbox of acct)
		if name of mb is "<<ORIGEN>>" then
			set srcBox to mb
			exit repeat
		end if
	end repeat
	if srcBox is missing value then return "NO_SOURCE"
	set msgs to messages of srcBox
	set total to count of msgs
	set n to <<LIMITE>>
	if total < n then set n to total
	set out to "TOTAL:" & total & linefeed
	repeat with i from 1 to n
		set m to item i of msgs
		try
			set mid to message id of m
		on error
			set mid to "unknown-" & i
		end try
		try
			set s to sender of m
		on error
			set s to "?"
		end try
		try
			set subj to subject of m
		on error
			set subj to "?"
		end try
		try
			set d to (date received of m) as string
		on error
			set d to "?"
		end try
		set out to out & "#" & i & " ||| " & d & " ||| " & s & " ||| " & subj & " ||| " & mid & linefeed
	end repeat
	return out
end tell


-- ───────────────────────────────────────────────────────────────
-- SCRIPT 1B — CUERPOS POR message-id (robusto + reanudable)
-- <<LISTA_MIDS>> = lista AppleScript ya escapada (campo
-- `lista_applescript` de escapar-applescript), en el MISMO orden que
-- las filas de metadatos que conservó el orquestador. El fichero
-- tbody_i.txt corresponde a la POSICIÓN i de esa lista, no a la
-- posición del correo en la carpeta → inmune a que entre correo nuevo.
--
-- Reanudable: el ORQUESTADOR filtra antes de llamar y pasa solo los
-- mids cuyo tbody_i.txt aún no existe o está vacío (checkpoint del
-- lado Python, para no pagar un `do shell script` por correo aquí).
-- Sublotes: llama a 1B con listas de <= resiliencia.sublote_con_cuerpo
-- (15) correos por invocación, no 50 de golpe.
-- ───────────────────────────────────────────────────────────────
set tbodyDir to (do shell script "d=\"$HOME/.email-triage/tmp\"; mkdir -p -m 700 \"$d\"; chmod 700 \"$d\"; printf %s \"$d\"")
tell application "Mail"
	set acct to account "<<CUENTA>>"
	set srcBox to missing value
	repeat with mb in (every mailbox of acct)
		if name of mb is "<<ORIGEN>>" then
			set srcBox to mb
			exit repeat
		end if
	end repeat
	if srcBox is missing value then return "NO_SOURCE"
	set idList to <<LISTA_MIDS>>
	set okN to 0
	set missN to 0
	repeat with i from 1 to (count of idList)
		set theID to item i of idList
		set p to tbodyDir & "/tbody_" & i & ".txt"
		set c to "(sin acceso al cuerpo)"
		try
			set hits to (messages of srcBox whose message id is theID)
			if (count of hits) > 0 then
				set c to content of (item 1 of hits)
				if (length of c) > 4000 then set c to text 1 thru 4000 of c
			else
				set missN to missN + 1
			end if
		on error
			set missN to missN + 1
		end try
		try
			set fref to open for access (POSIX file p) with write permission
			set eof of fref to 0
			write c to fref as «class utf8»
			close access fref
			if c is not "(sin acceso al cuerpo)" then set okN to okN + 1
		on error
			try
				close access (POSIX file p)
			end try
		end try
	end repeat
	return "bodies_ok:" & okN & " missing:" & missN & " of " & (count of idList)
end tell


-- NOTA (mejora opcional, subcomando helper): igual que `montar-mover`
-- emite el SCRIPT 3 entero ya escapado, conviene un `montar-leer-cuerpos`
-- que reciba {cuenta, origen, mids:[...]} y devuelva este SCRIPT 1B con
-- <<LISTA_MIDS>> ya montada desde `lista_applescript`. Cierra el mismo
-- hueco de "acordarse de escapar a mano" que ya cerró montar-mover.
--
-- SCRIPT 2 (crear buzones), SCRIPT 3 (mover por message-id) y SCRIPT 4
-- (limpieza) NO cambian respecto a v1: reutilízalos tal cual.
