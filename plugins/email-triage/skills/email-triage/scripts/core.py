#!/usr/bin/env python3
"""core.py — Fachada del NÚCLEO agnóstico (Fase A.2, split seguro).

Reexporta las funciones platform-agnostic de triage_helpers.py bajo nombres
limpios, para que cualquier consumidor (incluido el futuro adaptador Gmail)
haga `from core import scoring, sanitizar, ...` sin acoplarse al nombre del
fichero motor ni a nada de Mail.app.

Split SEGURO: NO mueve las ~2.700 líneas del motor —eso sería la Fase A.2
completa, deliberadamente diferida por riesgo/valor (ver MIGRACION-FASE-A.md
§5)—. Aquí solo se NOMBRA la frontera; `triage_helpers.py` sigue siendo la
única fuente de verdad y el comportamiento es idéntico.
"""
from triage_helpers import (
    cmd_sanitizar as sanitizar,
    cmd_scoring as scoring,
    cmd_scoring_dispatch as scoring_lote,
    cmd_ajustes as ajustes,
    cmd_agrupar_hilos as agrupar_hilos,
    cmd_validar_config as validar_config,
    cmd_gate_cuerpo as gate_cuerpo,
    cmd_calibrar as calibrar,
    cmd_registrar as registrar,
    cmd_compactar as compactar,
)

__all__ = [
    "sanitizar", "scoring", "scoring_lote", "ajustes", "agrupar_hilos",
    "validar_config", "gate_cuerpo", "calibrar", "registrar", "compactar",
]
