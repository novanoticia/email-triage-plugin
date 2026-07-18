-- ════════════════════════════════════════════════════════════════
-- Plantillas AppleScript consolidadas para email-triage (corrección #5)
-- Objetivo: reducir round-trips a osascript (cada uno ~60s en Mail).
-- Placeholders a sustituir (inventario que vigila test_contrato_skill.py):
--   <<CUENTA>>, <<ORIGEN>>, <<DESTINO_REVIEW>>, <<DESTINO_ARCHIVE>>  (nombre de
--     cuenta y de las carpetas; salen de tu config.yaml).
--   <<LISTA_REVIEW>>, <<LISTA_ARCHIVE>>  (las dos listas de message-ids).
-- REGLA DE ESCAPADO (obligatoria): pasa cuenta y carpetas por `escapar-applescript`
-- y sustituye con el campo `escapados`; rellena las dos listas de message-ids con
-- el campo `lista_applescript` del helper (o, mejor, deja que `montar-mover` emita
-- el SCRIPT 3 entero, que además cubre el archivo nativo y reply_needed). NUNCA
-- escribas un nombre o message-id crudo entre comillas: una comilla rompe el
-- literal e inyecta código.
-- Ejecutar escribiendo a /tmp con Desktop Commander y `osascript /tmp/x.scpt`
-- (los nombres con acentos rompen el inline — lección de producción #3).
-- ════════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────────────
-- SCRIPT 1 — LECTURA EN UNA SOLA PASADA
-- Devuelve metadatos (idx, fecha, remitente, asunto, message-id) Y
-- escribe el cuerpo crudo (<=4000) de cada correo a ~/.email-triage/tmp/tbody_N.txt.
-- Sustituye a 2 scripts previos (meta + bodies) = 1 round-trip en vez de 2.
-- ───────────────────────────────────────────────────────────────
-- Directorio temporal PRIVADO del usuario (700), NO /tmp: en macOS /tmp
-- es world-readable (sticky 1777) y cualquier usuario/proceso local podria
-- leer los cuerpos crudos mientras dura el triaje. Se crea aqui, se fija a
-- 700 y se limpian los cuerpos de ejecuciones anteriores.
set tbodyDir to (do shell script "d=\"$HOME/.email-triage/tmp\"; mkdir -p -m 700 \"$d\"; chmod 700 \"$d\"; printf %s \"$d\"")
do shell script "rm -f " & quoted form of tbodyDir & "/tbody_*.txt"

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
	set n to count of msgs
	if n > 50 then set n to 50
	set out to "TOTAL:" & (count of msgs) & linefeed
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
		try
			set c to content of m
			if (length of c) > 4000 then set c to text 1 thru 4000 of c
		on error
			set c to "(sin acceso al cuerpo)"
		end try
		set p to tbodyDir & "/tbody_" & i & ".txt"
		try
			set fref to open for access (POSIX file p) with write permission
			set eof of fref to 0
			write c to fref as «class utf8»
			close access fref
		on error errBody
			try
				close access (POSIX file p)
			end try
		end try
		set out to out & "#" & i & " ||| " & d & " ||| " & s & " ||| " & subj & " ||| " & mid & linefeed
	end repeat
	return out
end tell


-- ───────────────────────────────────────────────────────────────
-- SCRIPT 2 — CREAR Y VERIFICAR BUZONES DESTINO (paso aparte)
-- En iCloud `make new mailbox` reporta éxito aunque la carpeta tarde en
-- aparecer; por eso se crea AQUÍ, en su propio round-trip, y NO en el
-- mismo script que mueve. Tras esto, esperar ~3s antes de mover.
-- ───────────────────────────────────────────────────────────────
tell application "Mail"
	set acct to account "<<CUENTA>>"
	set res to ""
	repeat with bn in {"<<DESTINO_REVIEW>>", "<<DESTINO_ARCHIVE>>"}
		set found to false
		repeat with mb in (every mailbox of acct)
			if name of mb is bn then
				set found to true
				exit repeat
			end if
		end repeat
		if not found then
			try
				make new mailbox with properties {name:bn} at acct
				set res to res & bn & ":CREADA" & linefeed
			on error errMsg
				set res to res & bn & ":ERROR " & errMsg & linefeed
			end try
		else
			set res to res & bn & ":YA_EXISTIA" & linefeed
		end if
	end repeat
	return res
end tell


-- ───────────────────────────────────────────────────────────────
-- SCRIPT 3 — MOVER POR message-id + VERIFICAR (corrección #5)
-- Usa el filtro `whose` (robusto durante sincronización) en vez de
-- iterar `every message` (que lanza -1728 "no puede obtenerse item N").
-- Devuelve conteos para que el SKILL verifique en vez de fiarse del
-- valor de retorno. Rellenar las dos listas de message-ids.
--
-- ⚠️ SEGURIDAD (v3.8.4): el `message id` es una cabecera controlada por quien
-- envia el correo y NO pasa por el saneo S0. NO pegues message-ids crudos en
-- las listas de abajo: una comilla en un message-id cierra el literal y
-- AppleScript ejecuta lo que siga (`& (do shell script "...")`). Genera las dos
-- listas con el helper, que los valida y escapa, y pega su `lista_applescript`:
--   echo '{"valores":["<mid1>","<mid2>"]}' \
--     | python3 <ruta-del-skill>/scripts/triage_helpers.py escapar-applescript
-- O, mejor aun, deja que 'montar-mover' emita este SCRIPT 3 entero ya
-- escapado (cuenta, carpetas y message-ids) y no montes el literal a mano:
--   echo '{"cuenta":"...","origen":"...","destino_review":"...",
--          "destino_archive":"...","mids_review":[...],"mids_archive":[...]}' \
--     | python3 <ruta-del-skill>/scripts/triage_helpers.py montar-mover
-- Los placeholders MID_* de abajo son solo ilustrativos: sustituyelos por la
-- `lista_applescript` que devuelve el helper.
-- ───────────────────────────────────────────────────────────────
tell application "Mail"
	set acct to account "<<CUENTA>>"
	set srcBox to mailbox "<<ORIGEN>>" of acct
	set revBox to mailbox "<<DESTINO_REVIEW>>" of acct
	set arcBox to mailbox "<<DESTINO_ARCHIVE>>" of acct

	-- <<LISTA_REVIEW>> y <<LISTA_ARCHIVE>>: salida `lista_applescript` del
	-- helper escapar-applescript, NO message-ids pegados a mano.
	set toReview to {"MID_REVIEW_1", "MID_REVIEW_2"}
	set toArchive to {"MID_ARCHIVE_1", "MID_ARCHIVE_2"}

	set okRev to 0
	repeat with theID in toReview
		try
			set hits to (messages of srcBox whose message id is theID)
			if (count of hits) > 0 then
				move (item 1 of hits) to revBox
				set okRev to okRev + 1
			end if
		end try
	end repeat
	set okArc to 0
	repeat with theID in toArchive
		try
			set hits to (messages of srcBox whose message id is theID)
			if (count of hits) > 0 then
				move (item 1 of hits) to arcBox
				set okArc to okArc + 1
			end if
		end try
	end repeat

	delay 2
	-- Verificación real: cuántos quedan en origen vs cuántos se pidieron.
	return "movidos_review:" & okRev & "/" & (count of toReview) & ¬
		" movidos_archive:" & okArc & "/" & (count of toArchive) & ¬
		" | src_restantes:" & (count of (messages of srcBox))
end tell


-- ───────────────────────────────────────────────────────────────
-- SCRIPT 4 — LIMPIEZA (ejecutar al TERMINAR la consolidación)
-- Borra los cuerpos crudos ~/.email-triage/tmp/tbody_N.txt una vez el SKILL los ha
-- leído. El directorio ya es 700, pero el contenido de correo no debe
-- quedar en disco mas de lo necesario. Idempotente.
-- ───────────────────────────────────────────────────────────────
do shell script "rm -f \"$HOME/.email-triage/tmp\"/tbody_*.txt"
