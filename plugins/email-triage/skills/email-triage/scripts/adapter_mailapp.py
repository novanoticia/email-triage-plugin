#!/usr/bin/env python3
"""adapter_mailapp.py — Adaptador Mail.app del puerto AdaptadorCorreo (Fase A).

NO reescribe nada: ENVUELVE los subcomandos `montar-*` que triage_helpers.py
ya expone (ellos construyen el AppleScript; este adaptador lo ejecuta con
osascript y parsea el resultado a NormalizedEmail).

Diseño clave para testear sin un Mac: la CONSTRUCCIÓN de scripts (métodos
`construir_script_*`, puros, delegan en triage_helpers) se separa de la
EJECUCIÓN (`_run_osascript`, solo-Mac). En Linux/sandbox los `construir_*`
y los parsers son 100% testeables; solo la ejecución real requiere macOS.

Nota de contrato: los NOMBRES DE CARPETA destino son configuración del
adaptador (Mail.app mueve entre buzones), NO del puerto neutral —Gmail usaría
labels—. Por eso se fijan al construir el adaptador, no en la firma de mover().
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence

import triage_helpers as th
from contracts import (AdaptadorCorreo, AdaptadorNoDisponible, NormalizedEmail,
                       TIERS)

SEP = " ||| "
CENTINELA_SIN_ORIGEN = "NO_SOURCE"

# Carpetas por defecto (se sobrescriben con la config del usuario).
CARPETAS_DEFAULT = {
    "origen": "INBOX",
    "review": "Revisar",
    "archive": "",          # "" => buzón Archive nativo de la cuenta
    "reply_needed": "",     # "" o == origen => no se mueve
}


class MailAppAdapter(AdaptadorCorreo):
    """Backend macOS Mail.app vía AppleScript. Ejecución local; sin red."""

    nombre = "mailapp"
    # Mail.app NO tiene carpeta para reading_later: se declara para que el
    # orquestador no emita un tier que este backend dejaría en no-op.
    tiers_soportados = ("review", "archive", "reply_needed")

    def __init__(self, cuenta: str, carpetas: Optional[Mapping[str, str]] = None):
        self.cuenta = cuenta
        self.carpetas = dict(CARPETAS_DEFAULT)
        if carpetas:
            self.carpetas.update(carpetas)

    # ── Construcción de scripts (pura, testeable sin osascript) ──────────
    def construir_script_leer_bandeja(self, origen: Optional[str] = None,
                                      limite: int = 50,
                                      ventana_horas: Optional[int] = None) -> str:
        r = th.cmd_montar_leer_metadatos(
            {"cuenta": self.cuenta, "origen": origen or self.carpetas["origen"],
             "limite": limite, "ventana_horas": ventana_horas})
        return self._script_o_error(r)

    def construir_script_leer_cuerpos(self, handles: Sequence[str],
                                      origen: Optional[str] = None,
                                      prefijo: str = "/tmp/tbody_") -> str:
        r = th.cmd_montar_leer_cuerpos(
            {"cuenta": self.cuenta, "origen": origen or self.carpetas["origen"],
             "mids": list(handles), "prefijo": prefijo})
        return self._script_o_error(r)

    def construir_script_mover(self, movimientos: Mapping[str, Sequence[str]]
                               ) -> str:
        datos: Dict[str, Any] = {
            "cuenta": self.cuenta,
            "origen": self.carpetas["origen"],
            "destino_review": self.carpetas.get("review", ""),
            "destino_archive": self.carpetas.get("archive", ""),
            "destino_reply_needed": self.carpetas.get("reply_needed", ""),
        }
        for tier, handles in movimientos.items():
            datos["mids_" + tier] = list(handles)
        r = th.cmd_montar_mover(datos)
        return self._script_o_error(r)

    def construir_script_estado_hilo(self, clave_hilo: str,
                                     fecha_corte: Optional[str] = None) -> str:
        if not (isinstance(fecha_corte, str) and fecha_corte.strip()):
            raise ValueError(
                "MailAppAdapter.estado_hilo requiere fecha_corte no vacío "
                "(deriva del hilo; ver contrato del puerto).")
        r = th.cmd_montar_consulta_enviados(
            {"cuenta": self.cuenta, "clave_hilo": clave_hilo,
             "fecha_corte": fecha_corte})
        return self._script_o_error(r)

    @staticmethod
    def _script_o_error(r: Dict[str, Any]) -> str:
        if not isinstance(r, dict) or not r.get("ok"):
            raise ValueError("montar-* falló: %s" %
                             (r.get("error") if isinstance(r, dict) else r))
        return r["script"]

    # ── Parsers (puros, testeables) ──────────────────────────────────────
    def parsear_metadatos(self, salida: str) -> List[NormalizedEmail]:
        """SCRIPT 1A -> NormalizedEmail.

        Formato: 'TOTAL:<n>' y filas
            #<i> ||| <fecha> ||| <remitente> ||| <asunto> ||| <message-id>
        Centinela 'NO_SOURCE' si el buzón origen no existe.
        """
        salida = (salida or "").strip()
        if salida == CENTINELA_SIN_ORIGEN or not salida:
            return []
        correos: List[NormalizedEmail] = []
        for linea in salida.splitlines():
            linea = linea.rstrip("\r")
            if not linea or linea.startswith("TOTAL:"):
                continue
            partes = linea.split(SEP)
            if len(partes) < 5:
                continue  # fila malformada: se ignora, no revienta
            # El message-id es el ÚLTIMO campo; asunto/remitente no llevan SEP,
            # pero si el asunto lo llevara, el id sigue siendo la última parte.
            idx, fecha, remitente, asunto = partes[0], partes[1], partes[2], \
                SEP.join(partes[3:-1])
            mid = partes[-1]
            correos.append(NormalizedEmail(
                id=idx.strip().lstrip("#") or mid.strip(),
                handle=mid.strip(),
                remitente=remitente.strip(),
                asunto=asunto.strip(),
                fecha=fecha.strip(),
                cuerpo_leido=False))
        return correos

    @staticmethod
    def parsear_estado_hilo(salida: str) -> Optional[bool]:
        """Devuelve respuesta_pendiente (contrato): True=pendiente(+5),
        False=ya respondió(0), None=desconocido(+2). OJO al signo:
        'NO_RESPONDIDO' => pendiente => True."""
        s = (salida or "").strip().upper()
        if s.startswith("NO_RESPONDIDO"):
            return True   # el usuario NO respondió -> pendiente
        if s.startswith("RESPONDIDO"):
            return False  # ya respondió
        return None

    # ── Ejecución (solo-Mac) ─────────────────────────────────────────────
    def _run_osascript(self, script: str) -> str:
        if shutil.which("osascript") is None:
            raise AdaptadorNoDisponible(
                "osascript no disponible: MailAppAdapter solo opera en macOS "
                "con Mail.app abierto y permiso de Automatización.")
        proc = subprocess.run(["osascript", "-"], input=script,
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise AdaptadorNoDisponible("osascript falló: %s" % proc.stderr.strip())
        return proc.stdout

    # ── Puerto ───────────────────────────────────────────────────────────
    def leer_bandeja(self, origen: str = "", limite: int = 50,
                     ventana_horas: Optional[int] = None) -> List[NormalizedEmail]:
        script = self.construir_script_leer_bandeja(origen or None, limite,
                                                    ventana_horas)
        return self.parsear_metadatos(self._run_osascript(script))

    def leer_cuerpos(self, correos: Sequence[NormalizedEmail]
                     ) -> List[NormalizedEmail]:
        # La lectura real vuelca cuerpos a /tmp/tbody_N y el orquestador los
        # reasocia por handle. En Fase A el puerto queda definido; la
        # reasociación fina se hereda del flujo del SKILL.md (Fase A.2).
        raise AdaptadorNoDisponible(
            "leer_cuerpos: usar el flujo osascript+/tmp del SKILL.md; puerto "
            "definido para Fase A.2.")

    def estado_hilo(self, clave_hilo: str,
                    fecha_corte: Optional[str] = None) -> Optional[bool]:
        script = self.construir_script_estado_hilo(clave_hilo, fecha_corte)
        return self.parsear_estado_hilo(self._run_osascript(script))

    def mover(self, movimientos: Mapping[str, Sequence[str]]) -> Dict[str, Any]:
        no_sop = [t for t in movimientos if t not in self.tiers_soportados]
        if no_sop:
            return {"ok": False,
                    "error": "tier(s) no soportados por Mail.app: %s "
                             "(soportados: %s)" % (
                                 ", ".join(map(str, no_sop)),
                                 ", ".join(self.tiers_soportados))}
        script = self.construir_script_mover(movimientos)
        return {"ok": True, "salida": self._run_osascript(script).strip()}
