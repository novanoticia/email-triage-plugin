#!/usr/bin/env python3
"""Sonda de Apple `fm serve` (Foundation Models, modelos system y pcc).

Solo habla con 127.0.0.1 (sin proxy) y usa UN correo inventado. No toca
~/.email-triage, no lee el buzón y no necesita clave. Antes, en otra ventana
de Terminal:  fm serve --host 127.0.0.1 --port 8765
Herramienta de desarrollo (no se distribuye con el plugin). Ejecutar desde la
raíz del repositorio clonado: python3 scripts/sonda_fm.py. Resultados en
docs/mediciones-evaluadores.md.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

PUERTO = int(os.environ.get("FM_PUERTO", "8765"))
BASE = "http://127.0.0.1:%d/v1" % PUERTO
abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open

sys.path.insert(0, "plugins/email-triage/skills/email-triage/scripts")
import yaml  # noqa: E402
import evaluadores as ev  # noqa: E402


def peticion(ruta, cuerpo=None, timeout=180):
    if cuerpo is not None:
        cuerpo = dict(cuerpo, stream=False)  # sonda 1: por defecto respondía en streaming
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
                return r.status, "NO ES JSON: " + crudo.decode("utf-8", "replace")[:400], round(time.monotonic() - t, 1)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400], round(time.monotonic() - t, 1)
    except Exception as e:  # sin servidor, timeout…
        return None, "%s: %s" % (type(e).__name__, str(e)[:300]), round(time.monotonic() - t, 1)


def resumen(etiqueta, estado, datos, segundos):
    print("\n## %s -> HTTP %s en %ss" % (etiqueta, estado, segundos))
    if isinstance(datos, dict):
        print("   modelo:", datos.get("model"), "| usage:", datos.get("usage"))
        try:
            c = datos["choices"][0]
            print("   finish_reason:", c.get("finish_reason"))
            print("   contenido (inicio):", str(c["message"].get("content"))[:300])
        except Exception:
            print("   respuesta:", json.dumps(datos, ensure_ascii=False)[:400])
    else:
        print("  ", datos)


estado, datos, s = peticion("/models")
modelos = [m.get("id") for m in datos.get("data", [])] if isinstance(datos, dict) else []
print("## /v1/models -> HTTP %s:" % estado, modelos or datos)
if estado is None:
    sys.exit("No responde en %s. ¿Está `fm serve` abierto en otra ventana?" % BASE)
print("## /health ->", peticion("/health")[:2])

resumen("1. Prueba mínima (system)", *peticion("/chat/completions", {
    "model": "system", "messages": [{"role": "user", "content": "Responde solo: OK"}]}))

cfg = yaml.safe_load(open("plugins/email-triage/skills/email-triage/config.yaml", encoding="utf-8"))
p = ev.preparar({"perfil_minimo": "Coordino una asociación cultural ficticia.", "emails": [
    {"id": "1", "asunto": "¿Podemos vernos el jueves?", "remitente": "lucia@example.invalid",
     "cuerpo": "Necesito que decidamos antes del viernes si renovamos el convenio. ¿Te va el jueves?"}]})
mensajes = ev.mensajes(cfg, p["perfil_minimo"], p["emails"][0])
esquema = ev.esquema_evaluador(cfg)
print("\n## Tamaño de nuestra petición: %d caracteres de mensajes + %d de esquema"
      % (sum(len(m["content"]) for m in mensajes), len(json.dumps(esquema, ensure_ascii=False))))
formato = {"type": "json_schema", "json_schema": {
    "name": "evaluacion_correo", "strict": True, "schema": esquema}}

resumen("2. pcc: prueba mínima", *peticion("/chat/completions", {
    "model": "pcc", "messages": [{"role": "user", "content": "Responde solo: OK"}]}))
resumen("3. pcc: petición real CON esquema", *peticion("/chat/completions", {
    "model": "pcc", "messages": mensajes, "response_format": formato}))
resumen("4. pcc: petición real SIN esquema", *peticion("/chat/completions", {
    "model": "pcc", "messages": mensajes}))
