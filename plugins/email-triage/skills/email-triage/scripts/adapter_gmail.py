#!/usr/bin/env python3
"""adapter_gmail.py — Stub del adaptador Gmail (Fase A: NO implementado).

Existe para (1) fijar que el puerto AdaptadorCorreo es realmente cumplible por
un backend en la nube, y (2) marcar el trabajo diferido con un contrato claro,
no con una carpeta vacía. Cumple la INTERFAZ (es subclase concreta e
instanciable), pero cada verbo levanta NotImplementedError.

Cuando se aborde de verdad (ver MIGRACion-FASE-A.md, "Fase B"), este adaptador:
  - hablará con la API de Gmail (OAuth), no con osascript;
  - `handle` será el id de mensaje de Gmail (no un message-id RFC);
  - `estado_hilo` se resolverá con el threadId nativo (no con carpeta Enviados),
    normalmente SIN fecha_corte;
  - `mover` aplicará/quitará LABELS en vez de mover entre buzones.
El núcleo (sanitizar/scoring/agrupar-hilos/...) se reutiliza SIN cambios.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from contracts import AdaptadorCorreo, NormalizedEmail

_PENDIENTE = ("adaptador Gmail no implementado (Fase A). Ver "
              "MIGRACION-FASE-A.md → Fase B.")


class GmailAdapter(AdaptadorCorreo):
    """Backend Gmail (nube, API + OAuth). Stub hasta Fase B."""

    nombre = "gmail"

    def leer_bandeja(self, origen: str = "INBOX", limite: int = 50,
                     ventana_horas: Optional[int] = None) -> List[NormalizedEmail]:
        raise NotImplementedError(_PENDIENTE)

    def leer_cuerpos(self, correos: Sequence[NormalizedEmail]
                     ) -> List[NormalizedEmail]:
        raise NotImplementedError(_PENDIENTE)

    def estado_hilo(self, clave_hilo: str,
                    fecha_corte: Optional[str] = None) -> Optional[bool]:
        raise NotImplementedError(_PENDIENTE)

    def mover(self, movimientos: Mapping[str, Sequence[str]]) -> Dict[str, Any]:
        raise NotImplementedError(_PENDIENTE)
