#!/usr/bin/env python3
"""Compara el scoring base frente al ensayo P3 sobre los correos ficticios.

Herramienta de desarrollo (no se distribuye con el plugin). Lee
tests/ensayo_p3/correos.yaml, puntúa cada correo con el config.yaml de la
plantilla y con esa misma plantilla + la capa config-ensayo-p3.yaml, y
devuelve score, tier y cobertura de las dos configuraciones.

No usa red ni modelo: los veredictos son los etiquetados a mano en el
fichero. Mide el efecto MECÁNICO de la capa, no si un modelo elegiría esos
veredictos. Requiere PyYAML.

Uso:
  python3 scripts/ensayo_p3_comparar.py              # JSON por stdout
  python3 scripts/ensayo_p3_comparar.py --markdown   # tabla para docs/
"""
import argparse
import json
import os
import sys

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import triage_helpers as th  # noqa: E402

RUTA_CORREOS = os.path.join(RAIZ, "tests", "ensayo_p3", "correos.yaml")
RUTA_CFG = os.path.join(SKILL, "config.yaml")
RUTA_CAPA = os.path.join(SKILL, "config-ensayo-p3.yaml")


def _puntua(correo, cfg, grupo):
    """Scoring determinista con el contrato P2 encendido, solo para leer la
    cobertura: P2 no altera score ni tier (lo fija tests/test_contrato_p2)."""
    cfg = th._merge_config(cfg, {"scoring": {"contrato_p2": True}})
    payload = {
        "verdicts": {**correo["comunes"], **(correo.get(grupo) or {})},
        "hard_rules": correo.get("hard_rules") or [],
        "forzar_reply_needed": bool(correo.get("forzar_reply_needed")),
    }
    r = th.cmd_scoring(payload, cfg)
    return {
        "score": r["score"],
        "tier": r["tier"],
        "ejes": r["ejes"],
        "ejes_sin_clampar": r["ejes_sin_clampar"],
        "core_sin_explicar": r["cobertura"]["core_sin_explicar"],
        "ignorados": r["ignorados"],
    }


def comparar(ruta_correos=RUTA_CORREOS):
    with open(ruta_correos, encoding="utf-8") as f:
        correos = yaml.safe_load(f)["correos"]
    base = th._cargar_config(RUTA_CFG)
    ensayo = th._fusiona_config_ensayo(base, RUTA_CAPA)
    filas = []
    for c in correos:
        a, b = _puntua(c, base, "base"), _puntua(c, ensayo, "ensayo")
        # Saturación: algún eje recortado por su rango en alguna config,
        # que puede ocultar el efecto del ensayo (hallazgo D / P1).
        saturados = sorted({e for r in (a, b) for e in r["ejes"]
                            if r["ejes"][e] != r["ejes_sin_clampar"][e]})
        filas.append({
            "id": c["id"], "caso": c["caso"],
            "base": a, "ensayo": b,
            "delta": b["score"] - a["score"],
            "cambia_tier": a["tier"] != b["tier"],
            "ejes_saturados": saturados,
            "juicio": " ".join(str(c.get("juicio", "")).split()),
        })
    return {
        "correos": filas,
        "resumen": {
            "total": len(filas),
            "cambian_tier": sum(f["cambia_tier"] for f in filas),
            "suben": sum(f["delta"] > 0 for f in filas),
            "bajan": sum(f["delta"] < 0 for f in filas),
            "iguales": sum(f["delta"] == 0 for f in filas),
        },
    }


def a_markdown(res):
    lineas = ["| Correo | Base | Ensayo | Δ | Ejes saturados |",
              "|---|---|---|---|---|"]
    for f in res["correos"]:
        tier_e = ("**%s**" % f["ensayo"]["tier"] if f["cambia_tier"]
                  else f["ensayo"]["tier"])
        lineas.append("| %s | %s %s | %s %s | %+d | %s |" % (
            f["caso"], f["base"]["score"], f["base"]["tier"],
            f["ensayo"]["score"], tier_e, f["delta"],
            ", ".join(f["ejes_saturados"]) or "—"))
    return "\n".join(lineas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--markdown", action="store_true",
                    help="tabla Markdown en lugar de JSON")
    args = ap.parse_args(argv)
    res = comparar()
    if args.markdown:
        print(a_markdown(res))
    else:
        json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
        print()


if __name__ == "__main__":
    main()
