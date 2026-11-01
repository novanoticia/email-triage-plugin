#!/usr/bin/env python3
"""Sonda de Ollama local antes de escribir los adaptadores `local`.

Solo habla con 127.0.0.1:11434 (sin proxy) y usa UN correo inventado. No toca
~/.email-triage, no lee el buzón y no necesita clave. Antes, con Ollama
cerrado, en otra ventana de Terminal:
    OLLAMA_CONTEXT_LENGTH=16384 ollama serve
(con 16 GB, Ollama usa 4.096 tokens por defecto y recortaría la petición).
Herramienta de desarrollo (no se distribuye con el plugin). Ejecutar desde la
raíz del repositorio clonado; modelos por variable:
    LLM=qwen3.5:latest DECISION="tev1:4b d1:latest" python3 scripts/sonda_ollama.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:%s" % os.environ.get("OLLAMA_PUERTO", "11434")
LLM = os.environ.get("LLM", "qwen3.5:latest")
DECISION = os.environ.get("DECISION", "tev1:4b d1:latest").split()
abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open

sys.path.insert(0, "plugins/email-triage/skills/email-triage/scripts")
import yaml  # noqa: E402
import clasificadores as nc  # noqa: E402
import evaluadores as ev  # noqa: E402
import jev as j  # noqa: E402


def peticion(ruta, cuerpo=None, timeout=600):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(BASE + ruta, data=datos, method="POST" if datos else "GET",
                                 headers={"Content-Type": "application/json"})
    t = time.monotonic()
    try:
        with abrir(req, timeout=timeout) as r:
            crudo = r.read()
            try:
                return r.status, json.loads(crudo), round(time.monotonic() - t, 1)
            except ValueError:
                return r.status, "NO ES JSON: " + crudo.decode("utf-8", "replace")[:300], round(time.monotonic() - t, 1)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400], round(time.monotonic() - t, 1)
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, str(e)[:300]), round(time.monotonic() - t, 1)


estado, datos, _ = peticion("/api/version")
print("## Ollama:", estado, datos)
if estado is None:
    sys.exit("No responde en %s. ¿Está `ollama serve` abierto?" % BASE)
estado, datos, _ = peticion("/api/tags")
print("## Modelos:", [m.get("name") for m in datos.get("models", [])] if isinstance(datos, dict) else datos)

cfg = yaml.safe_load(open("plugins/email-triage/skills/email-triage/config.yaml", encoding="utf-8"))
perfil = "Coordino una asociación cultural ficticia."
correo = {"id": "1", "asunto": "¿Podemos vernos el jueves?", "remitente": "lucia@example.invalid",
          "cuerpo": "Necesito que decidamos antes del viernes si renovamos el convenio. ¿Te va el jueves?"}

# --- 1. LLM generalista por Chat Completions, como los evaluadores ---
p = ev.preparar({"perfil_minimo": perfil, "emails": [correo]})
e = p["emails"][0]
mensajes = ev.mensajes(cfg, perfil, e)
esquema = ev.esquema_evaluador(cfg)
cuerpo = {"model": LLM, "messages": mensajes, "stream": False, "reasoning_effort": "none",
          "response_format": {"type": "json_schema", "json_schema": {
              "name": "evaluacion_correo", "strict": True, "schema": esquema}}}
estado, datos, s = peticion("/v1/chat/completions", cuerpo)
print("\n## 1. LLM %s (Chat Completions con esquema) -> HTTP %s en %ss" % (LLM, estado, s))
if isinstance(datos, dict):
    print("   model:", datos.get("model"), "| usage:", datos.get("usage"))
    try:
        c = datos["choices"][0]
        print("   finish_reason:", c.get("finish_reason"))
        contenido = ev.extraer_chat(datos)
        errs = __import__("esquema").errores(contenido, esquema)
        print("   cumple el esquema:", not errs, ("" if not errs else str(errs)[:200]))
        fila = contenido["evaluaciones"][0]
        import triage_helpers as th
        print("   eco correcto:", th.eco_coincide(fila.get("eco"), th.ancla_extracto(e["estado"]["texto"])))
        print("   dudas:", len(fila.get("dudas") or []))
    except Exception as exc:
        print("   no se pudo leer la respuesta:", type(exc).__name__, str(exc)[:200])
else:
    print("  ", datos)
estado, datos, _ = peticion("/api/ps")
for m in (datos.get("models", []) if isinstance(datos, dict) else []):
    print("   en memoria:", m.get("name"), "| contexto:", m.get("context_length"), "| tamaño:", m.get("size"))

# --- 2. Modelos de decisión por /v1/systemone, como Jev ---
pj = j.preparar({"perfil_minimo": perfil, "emails": [correo]})
activos = nc._opciones(cfg)
preguntas = j._preguntas(cfg, activos)
for modelo in DECISION:
    cuerpo = j._cuerpo(modelo, perfil, pj["emails"][0]["estado"], preguntas)
    estado, datos, s = peticion("/v1/systemone", cuerpo)
    print("\n## 2. Decisión %s (/v1/systemone, %d preguntas) -> HTTP %s en %ss"
          % (modelo, len(preguntas), estado, s))
    if not isinstance(datos, dict):
        print("  ", datos)
        continue
    print("   model:", datos.get("model"), "| usage:", datos.get("usage"))
    try:
        v = nc.validar_forma(j.a_forma_interna(datos, preguntas),
                             {k: q["criteria"] for k, q in preguntas.items()}, "local")
        conf = sorted(v["confianzas"].values())
        print("   respuesta válida | inciertos:", len(v["inciertos"]), "| no_aplica:", len(v["no_aplica"]),
              "| confianza mín/mediana:", round(conf[0], 3), round(conf[len(conf) // 2], 3))
    except Exception as exc:
        print("   respuesta no válida:", type(exc).__name__, str(exc)[:200])
        print("   inicio:", json.dumps(datos, ensure_ascii=False)[:300])
