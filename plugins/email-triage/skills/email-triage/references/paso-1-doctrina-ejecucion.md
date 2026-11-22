# Ejecución y reintentos de lectura de Mail.app

Lanza `scripts/leer_mailapp.py` como un único proceso. Usa la ejecución en
segundo plano del host si su espera síncrona no cubre el plazo de lectura y
espera el resultado del propio proceso. El lector limita cada llamada a
AppleScript y produce JSON saneado. Si el host termina la espera sin confirmar
que el proceso se ha detenido, comprueba el estado de ese proceso antes de
relanzar. Evita terminar instancias de otras sesiones.

## Metadatos y cuerpos en sublotes

Resuelve primero los metadatos saneados con `operacion: "metadatos"`. Solicita
los cuerpos de las filas elegidas, con `sublote` igual a
`resiliencia.sublote_con_cuerpo`. El lector consulta el buzón de la cuenta
identificada por `mail_account_id` y vincula cada respuesta al `mail_id` local
y al `message_id` esperado. La posición de la fila puede variar sin afectar
a la asociación.

## Reintentos

Una llamada fallida se repite desde el JSON de solicitud. Se pueden volver
a pedir solo los pares sin respuesta saneada de identidad verificada.
Nunca uses `tbody_*.txt`, prefijos de lote, índices de buzón, tamaños de
archivo ni la salida cruda de AppleScript como prueba de lectura. El lector
no genera archivos con correo crudo. Si la cuenta, el buzón o los
identificadores ya no coinciden, vuelve a capturar los metadatos antes de
preparar una nueva evaluación.

## Aviso de primera ejecución en modo veloz

En veloz se anuncia "salta calibración, reutiliza caché". Pero si NO hay caché
(`calibrar --leer` devuelve `vigente:false`), corre igualmente la lectura lenta
del historial. **El primer veloz nunca es veloz.** Avísalo:

> ⏳ Primera ejecución: no hay calibración cacheada, la genero ahora (una lectura
> extra del historial). Las siguientes sesiones veloces reutilizarán la caché.
