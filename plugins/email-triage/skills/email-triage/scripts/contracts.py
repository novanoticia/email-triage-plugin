#!/usr/bin/env python3
"""contracts.py — Frontera core ↔ adaptador de correo (Fase A).

Superficie ÚNICA de intercambio entre el NÚCLEO agnóstico de scoring
(triage_helpers.py) y cualquier BACKEND de correo (Mail.app hoy; Gmail mañana).

El núcleo NUNCA sabe de dónde viene el correo ni cómo se mueve: consume
`NormalizedEmail` y emite decisiones de tier. Cada adaptador traduce SU mundo a
`NormalizedEmail` y ejecuta los movimientos, cumpliendo `AdaptadorCorreo`.

Platform-agnostic a propósito: no importa osascript, ni triage_helpers, ni
ninguna API. Es el contrato, no una implementación. Ver ARCHITECTURE.md.

Los invariantes de esta frontera (endurecidos tras revisión adversarial) están
documentados campo a campo abajo; respétalos en cada adaptador.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Mapping, Optional, Sequence

# Tiers canónicos. `mover` los recibe como claves; NO todo adaptador realiza
# todos (ver AdaptadorCorreo.tiers_soportados).
TIERS = ("reply_needed", "review", "reading_later", "archive")


@dataclass
class NormalizedEmail:
    """Objeto de intercambio que un adaptador PRODUCE y el núcleo CONSUME.

    Lleva el correo CRUDO (pre-sanitización): limpiar (S0–S5) y puntuar es
    trabajo del núcleo, no del adaptador.

    IDENTIDAD vs OPERACIÓN (frontera explícita):
      id      Identidad estable para deduplicar / "ya visto" dentro y entre
              lotes. El núcleo la usa para agrupar y no repetir.
      handle  Asa OPACA de OPERACIÓN: lo que el adaptador necesita para leer o
              mover ESTE mensaje. Mail.app: message-id RFC (global). Gmail: id
              de mensaje (scoped a la cuenta). El núcleo nunca lo interpreta.
    GRANULARIDAD: `handle`/`mover` operan a nivel MENSAJE; `clave_hilo`/
    `estado_hilo` operan a nivel HILO. No se mezclan.

    Invariantes de campo:
      remitente, asunto   Texto CRUDO (lo sanea el núcleo con S0).
      cuerpo_crudo        Cuerpo tal como lo entrega el backend (texto o HTML o
                          vacío si aún no se leyó). NO se normaliza aquí: el
                          subcomando `sanitizar` del núcleo decodifica/limpia
                          HTML/base64. "" si cuerpo_leido es False.
      fecha               ISO-8601. Recomendado UTC tz-aware para que
                          `ventana_horas` y `fecha_corte` comparen igual entre
                          backends. (Deuda: el adaptador Mail.app hoy pasa la
                          cadena nativa de AppleScript; normalizar a UTC es
                          trabajo pendiente — ver MIGRACION-FASE-A.md §7.)
      clave_hilo          Clave de agrupación de hilo (Re:/Fwd: normalizado o
                          threadId nativo). None si no aplica.
      respuesta_pendiente Señal verificada del "+5 el usuario es el blocker".
                          Nombre y signo apuntan al mismo lado:
                            True  -> respuesta PENDIENTE (el usuario no ha
                                     respondido) -> aplica +5
                            None  -> desconocido -> +2
                            False -> ya respondió -> 0
                          PROHIBIDO evaluarla por truthiness: `if not
                          respuesta_pendiente` colapsaría False(+0) y None(+2),
                          que puntúan distinto. Comparar SIEMPRE con is
                          True/False/None. La resuelve el adaptador (Mail.app:
                          carpeta Enviados; Gmail: hilo nativo).
      remitente_en_historial  ¿El usuario conserva a este remitente? Atenúa
                          sender_bulk. La puebla el adaptador/orquestador desde
                          el historial + config; NO es un verbo del puerto
                          porque es config-driven, no una consulta viva.
                          True/False/None (None = sin dato).
      cuerpo_leido        True solo si cuerpo_crudo procede de una lectura real.
      adapter_private     Passthrough PRIVADO del adaptador (p. ej. reconectar
                          handle con su objeto de API entre leer y mover). El
                          núcleo NUNCA debe leerlo; el nombre lo señala para que
                          cualquier acceso desde el núcleo cante en revisión.
    """
    id: str
    handle: str
    remitente: str = ""
    asunto: str = ""
    cuerpo_crudo: str = ""
    fecha: Optional[str] = None
    clave_hilo: Optional[str] = None
    respuesta_pendiente: Optional[bool] = None
    remitente_en_historial: Optional[bool] = None
    cuerpo_leido: bool = False
    adapter_private: Dict[str, Any] = field(default_factory=dict)

    def validar(self) -> None:
        """Lanza ValueError si faltan los campos mínimos que el núcleo exige."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("NormalizedEmail.id vacío o no-texto")
        if not isinstance(self.handle, str) or not self.handle.strip():
            raise ValueError("NormalizedEmail.handle vacío o no-texto")
        # Tri-estado estricto: nada de truthiness (ver docstring del campo).
        if self.respuesta_pendiente not in (True, False, None):
            raise ValueError("respuesta_pendiente debe ser True/False/None")
        if self.remitente_en_historial not in (True, False, None):
            raise ValueError("remitente_en_historial debe ser True/False/None")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "NormalizedEmail":
        campos = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**campos)


class AdaptadorNoDisponible(RuntimeError):
    """El backend no puede operar en este entorno (p. ej. osascript ausente)."""


class AdaptadorCorreo(ABC):
    """Puerto que todo backend de correo debe cumplir.

    Deliberadamente mínimo: solo los cuatro verbos que el orquestador necesita.
    NO se añaden métodos "por si acaso" de otra plataforma (borrado, marcar
    leído, dry-run): se ampliará el puerto cuando un flujo REAL lo pida, no para
    un Gmail que aún no existe.
    """

    nombre: str = "abstracto"

    #: Tiers que ESTE adaptador realiza de verdad. El orquestador debe
    #: consultarlo antes de emitir un tier: no todo backend enruta los cuatro
    #: (p. ej. Mail.app no tiene carpeta para 'reading_later').
    tiers_soportados: Sequence[str] = TIERS

    @abstractmethod
    def leer_bandeja(self, origen: str, limite: int = 50,
                     ventana_horas: Optional[int] = None) -> List[NormalizedEmail]:
        """Metadatos (sin cuerpos) de la bandeja `origen`.

        `origen` es un identificador ABSTRACTO de buzón/etiqueta (no una ruta de
        plataforma). `ventana_horas`: si se da, solo mensajes de esa ventana.
        Diseñado para triaje de ventana reciente: `ventana_horas` acota el
        conjunto y NO hay cursor de paginación (YAGNI; si un caso real necesita
        página 2, se añade entonces). Devuelve correos con cuerpo_leido=False.
        """
        raise NotImplementedError

    @abstractmethod
    def leer_cuerpos(self, correos: Sequence[NormalizedEmail]
                     ) -> List[NormalizedEmail]:
        """Enriquece con cuerpo. Garantía de correspondencia:

        devuelve los MISMOS correos (por id), en el MISMO orden, 1-a-1. Un fallo
        de lectura deja cuerpo_crudo="" y cuerpo_leido=False para ESE correo;
        NUNCA lo omite (omitir rompería el alineamiento por índice).
        """
        raise NotImplementedError

    @abstractmethod
    def estado_hilo(self, clave_hilo: str,
                    fecha_corte: Optional[str] = None) -> Optional[bool]:
        """Resuelve `respuesta_pendiente` para un hilo (True/False/None).

        `fecha_corte` (ISO-8601): punto a partir del cual buscar una respuesta
        del usuario. Es OBLIGATORIO para backends basados en carpeta (Mail.app
        lo exige) y OPCIONAL para los que resuelven por hilo nativo (Gmail vía
        threadId). Un backend que lo requiera y no lo reciba debe lanzar
        ValueError con mensaje de contrato, no fallar de forma opaca.
        """
        raise NotImplementedError

    @abstractmethod
    def mover(self, movimientos: Mapping[str, Sequence[str]]) -> Dict[str, Any]:
        """Mueve mensajes a carpetas/labels por tier (granularidad MENSAJE).

        `movimientos`: {tier: [handle, ...]} con tiers en `tiers_soportados`.
        Un tier no soportado se reporta como error, no como no-op silencioso.
        Los NOMBRES de carpeta/label destino son CONFIG del adaptador, no van
        aquí (Mail.app mueve entre buzones; Gmail aplicaría labels).
        Resultado: {"ok": bool, ...}. Cuando el backend permite fallo parcial
        (p. ej. un handle ya no existe), el resultado debe poder reportar qué
        handles fallaron, no solo un ok global.
        """
        raise NotImplementedError

    def capacidades(self) -> Dict[str, Any]:
        return {"nombre": self.nombre, "tiers_soportados": list(self.tiers_soportados)}
