#!/usr/bin/env python3
"""Lectura de Mail.app que sanea cuerpo y metadatos antes de emitirlos.

El JSON crudo de AppleScript solo circula por el pipe privado del subproceso.
Cada lectura de cuerpo verifica cuenta e identidad. Una reanudación repite
la lectura solicitada y jamás reutiliza ficheros crudos ni índices de buzón.
"""

import json
from pathlib import Path
import re
import subprocess
import sys

import triage_helpers as th


_SCRIPT = Path(__file__).with_suffix(".applescript")
_MAX_LOTE = 500
_ACCOUNT_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")
# Subconjunto interoperable de Message-ID, con los delimitadores de Mail
# si los trae. Se conserva el valor exacto para compararlo en otra lectura.
_MID = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+")
_ERRORES_ORIGEN = {
    "sin_cuenta", "cuenta_ambigua", "cuenta_cambiada",
    "sin_buzon", "buzon_ambiguo",
}


class ErrorCaptura(Exception):
    """Error con código estable y sin contenido del buzón."""


def _mid_seguro(valor):
    if not isinstance(valor, str) or len(valor) > 998:
        return False
    candidato = valor[1:-1] if valor.startswith("<") and valor.endswith(">") else valor
    return bool(_MID.fullmatch(candidato)) and not th._detectar_s0(candidato)


def _entero(valor, minimo, maximo):
    return type(valor) is int and minimo <= valor <= maximo


def _identidad(valor):
    # Mail declara id como entero. Nunca se usan índices de carpeta.
    return _entero(valor, 1, 2**53 - 1)


def _capturar(argumentos):
    try:
        proceso = subprocess.run(
            ["/usr/bin/osascript", str(_SCRIPT), *argumentos],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=True, timeout=180,
        )
        resultado = json.loads(proceso.stdout)
    except subprocess.TimeoutExpired:
        raise ErrorCaptura("tiempo_agotado") from None
    except (subprocess.CalledProcessError, OSError):
        raise ErrorCaptura("mailapp_inaccesible") from None
    except (ValueError, RecursionError):
        raise ErrorCaptura("respuesta_mail_invalida") from None
    if isinstance(resultado, list) and len(resultado) == 1:
        codigo = resultado[0]
        if isinstance(codigo, str) and codigo in _ERRORES_ORIGEN:
            raise ErrorCaptura(codigo)
    if not (
        isinstance(resultado, list)
        and len(resultado) == 4
        and resultado[0] == "ok"
        and isinstance(resultado[1], str)
        and _ACCOUNT_ID.fullmatch(resultado[1])
        and type(resultado[2]) is int
        and resultado[2] >= 0
        and isinstance(resultado[3], list)
    ):
        raise ErrorCaptura("respuesta_mail_invalida")
    _, cuenta, total, filas = resultado
    return cuenta, total, filas


def _saneado(fila, max_chars):
    mail_id, mid, remitente, asunto, fecha, acceso, cuerpo = fila
    limpio = th.cmd_sanitizar(cuerpo, max_chars, asunto, remitente)
    for clave in ("asunto_evaluable", "remitente_evaluable"):
        # Mantener un solo campo por cabecera tras S0. También limpia los
        # invisibles con el mismo criterio del cuerpo.
        limpio[clave] = " ".join(th._limpiar_visible(limpio[clave]).split())
    if acceso != "cuerpo" and not limpio["injection"]:
        limpio["etiqueta"] = "[solo metadatos]"
    return {
        **limpio,
        "id": mail_id,
        "mail_id": mail_id,
        "message_id": mid if _mid_seguro(mid) else None,
        "fecha": fecha,
        "asunto": limpio["asunto_evaluable"],
        "remitente": limpio["remitente_evaluable"],
        "cuerpo_leido": acceso == "cuerpo",
    }


def _filas_verificadas(filas, accesos):
    salidas = {}
    for fila in filas:
        if not (
            isinstance(fila, list) and len(fila) == 7
            and _identidad(fila[0]) and fila[0] not in salidas
            and all(isinstance(campo, str) for campo in fila[1:])
            and fila[5] in accesos
            and (fila[5] == "cuerpo" or not fila[6])
        ):
            raise ErrorCaptura("respuesta_mail_invalida")
        salidas[fila[0]] = fila
    return salidas


def leer(datos):
    if not isinstance(datos, dict):
        raise ErrorCaptura("peticion_invalida")
    cuenta, origen = datos.get("cuenta"), datos.get("origen")
    if any(
        not isinstance(nombre, str) or not nombre.strip() or "\0" in nombre
        for nombre in (cuenta, origen)
    ):
        raise ErrorCaptura("origen_invalido")
    operacion = datos.get("operacion", "metadatos")
    max_chars = datos.get("max_chars", 1500)
    if not _entero(max_chars, 1, th.MAX_ENTRADA_SANITIZAR):
        raise ErrorCaptura("max_chars_invalido")
    argumentos = [operacion, cuenta, origen, str(th.MAX_ENTRADA_SANITIZAR)]
    correos = []
    no_disponibles = []

    if operacion == "metadatos":
        limite = datos.get("limite", 50)
        ventana = datos.get("ventana_horas")
        if not _entero(limite, 1, _MAX_LOTE) or (
            ventana is not None and not _entero(ventana, 1, 24 * 365)
        ):
            raise ErrorCaptura("limite_o_ventana_invalido")
        id_cuenta, total, filas = _capturar(
            [*argumentos, "", str(limite), str(ventana or 0)]
        )
        if len(filas) != min(limite, total):
            raise ErrorCaptura("respuesta_mail_invalida")
        for mail_id, fila in _filas_verificadas(filas, {"metadatos", "no_disponible"}).items():
            if fila[5] == "no_disponible":
                no_disponibles.append(mail_id)
            else:
                correos.append(_saneado(fila, max_chars))
    elif operacion == "cuerpos":
        id_cuenta = datos.get("mail_account_id")
        peticiones = datos.get("correos")
        sublote = datos.get("sublote", 15)
        if not (
            isinstance(id_cuenta, str) and _ACCOUNT_ID.fullmatch(id_cuenta)
            and isinstance(peticiones, list) and len(peticiones) <= _MAX_LOTE
            and _entero(sublote, 1, 50)
        ):
            raise ErrorCaptura("peticion_cuerpos_invalida")
        esperados = {}
        for peticion in peticiones:
            if not isinstance(peticion, dict):
                raise ErrorCaptura("identidad_invalida")
            mail_id, mid = peticion.get("mail_id"), peticion.get("message_id")
            if not _identidad(mail_id) or mail_id in esperados or not _mid_seguro(mid):
                raise ErrorCaptura("identidad_invalida")
            esperados[mail_id] = mid
        ids = list(esperados)
        total = len(ids)
        for inicio in range(0, total, sublote):
            bloque = ids[inicio:inicio + sublote]
            cuenta_capturada, n, filas = _capturar([
                *argumentos, id_cuenta, str(th._EXTRACCION_CRUDA),
                *map(str, bloque),
            ])
            if cuenta_capturada != id_cuenta:
                raise ErrorCaptura("cuenta_cambiada")
            validadas = _filas_verificadas(filas, {"cuerpo", "sin_cuerpo", "no_disponible"})
            if n != len(bloque) or set(validadas) != set(bloque):
                raise ErrorCaptura("respuesta_mail_invalida")
            for mail_id in bloque:
                fila = validadas[mail_id]
                if fila[5] == "no_disponible" or fila[1] != esperados[mail_id]:
                    no_disponibles.append(mail_id)
                else:
                    correos.append(_saneado(fila, max_chars))
    else:
        raise ErrorCaptura("operacion_invalida")
    return {
        "ok": True,
        "operacion": operacion,
        "cuenta": cuenta,
        "origen": origen,
        "mail_account_id": id_cuenta,
        "total": total,
        "correos": correos,
        "mail_ids_no_disponibles": no_disponibles,
    }


def main():
    try:
        datos = json.load(sys.stdin)
        resultado = leer(datos)
    except ErrorCaptura as exc:
        resultado = {"ok": False, "error": str(exc)}
    except (ValueError, RecursionError, OSError):
        resultado = {"ok": False, "error": "peticion_invalida"}
    print(json.dumps(resultado, ensure_ascii=True))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
