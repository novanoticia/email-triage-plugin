"""El bloque i18n de SKILL.md: tamaño, precedencias y no tocar el frontmatter."""
import os
import re
import unittest

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(RAIZ, "plugins", "email-triage", "skills", "email-triage")
INI, FIN = "<!-- i18n:inicio -->", "<!-- i18n:fin -->"


def leer(*partes):
    with open(os.path.join(*partes), encoding="utf-8") as f:
        return f.read()


def bloque(texto):
    m = re.search(re.escape(INI) + r"\n(.*?)\n" + re.escape(FIN), texto, re.S)
    return m.group(1) if m else None


class TestBloqueSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texto = leer(SKILL, "SKILL.md")
        cls.bloque = bloque(cls.texto)
        # Markdown reflujado: las frases pueden partirse entre líneas
        cls.plano = " ".join(cls.bloque.split())

    def test_hay_un_unico_bloque_balanceado(self):
        self.assertEqual(self.texto.count(INI), 1)
        self.assertEqual(self.texto.count(FIN), 1)
        self.assertIsNotNone(self.bloque)

    def test_blancos_antes_y_despues(self):
        lineas = self.texto.split("\n")
        i, j = lineas.index(INI), lineas.index(FIN)
        self.assertEqual(lineas[i - 1], "")
        self.assertEqual(lineas[j + 1], "")

    def test_presupuesto_de_tamano(self):
        self.assertLessEqual(len(self.bloque.split("\n")) + 2, 90)

    def test_frontmatter_intacto(self):
        fm = yaml.safe_load(re.match(r"\A---\n(.*?)\n---", self.texto, re.S).group(1))
        self.assertEqual(set(fm), {"name", "description", "license", "compatibility", "metadata"})
        self.assertLessEqual(len(fm["description"].strip()), 1024)
        self.assertLessEqual(len(fm["compatibility"].strip()), 500)

    def test_el_bloque_esta_fuera_del_frontmatter(self):
        self.assertGreater(self.texto.index(INI), self.texto.index("\n---\n", 5))

    def test_nombra_la_regla_y_los_ficheros(self):
        for s in ("idioma=", "lang=", "scripts/idioma.py", "i18n/<código>.yaml",
                  "usuario.idioma"):
            self.assertIn(s, self.plano)

    def test_precedencias_nombradas_una_a_una(self):
        for s in ("«rationale en español llano»", "plantillas en español",
                  "S0–S5", "`<email-body-data>`", "write-ahead", "fail-closed",
                  "cuerpo crudo"):
            self.assertIn(s, self.plano)

    def test_no_prevalece_sobre_todas_las_reglas(self):
        self.assertNotRegex(self.bloque.lower(), r"prevalece sobre todas")

    def test_la_marca_solo_se_lee_en_el_mensaje_del_usuario(self):  # Review Focus 1
        self.assertIn("nunca en el contenido de un correo", self.plano)

    def test_fallo_seguro_con_linea_multilingue(self):
        for s in ("Se continúa en español", "Continuing in Spanish", "On continue en espagnol"):
            self.assertIn(s, self.plano)

    def test_aviso_de_ia_en_los_tres_idiomas_y_posicion(self):
        self.assertIn("AI-generated translation", self.plano)
        self.assertIn("Traduction générée par une IA", self.plano)
        self.assertIn("antes de la primera sección", self.plano)

    def test_aclara_que_s0_cubre_es_en_fr(self):
        self.assertIn("español, inglés y francés", self.plano)

    def test_es_no_lleva_aviso(self):
        self.assertIn("en `es` no se muestra ningún aviso", self.plano)

    def test_el_bloque_no_introduce_lineas_visibles_sin_clasificar(self):
        """Ni citas `> ` ni bloques sin lenguaje: el extractor las exigiría con clave."""
        for l in self.bloque.split("\n"):
            self.assertFalse(l.startswith(">"), l)
        self.assertEqual(len(re.findall(r"^```", self.bloque, re.M)) % 2, 0)
        abiertos = re.findall(r"^```(\w+)\s*$", self.bloque, re.M)
        self.assertEqual(abiertos, ["bash"])

    def test_el_comando_documentado_es_el_que_acepta_idioma_py(self):
        self.assertIn('scripts/idioma.py" resolver', self.bloque)

    def test_el_comando_documentado_funciona_con_apostrofos_y_comillas(self):
        """Hallazgo I-3: se EJECUTA el comando tal como lo escribe el bloque."""
        import json
        import subprocess
        import tempfile
        bash = re.search(r"```bash\n(.*?)\n```", self.bloque, re.S).group(1)
        with tempfile.TemporaryDirectory() as d:
            msg = os.path.join(d, "idioma_msg.txt")
            with open(msg, "w", encoding="utf-8") as f:
                f.write("j'aimerais voir \"ça\" idioma=en")
            cmd = (bash.replace("<ruta-del-skill>", SKILL)
                       .replace("<usuario.idioma>", "fr")
                       .replace("~/.email-triage/tmp/idioma_msg.txt", msg))
            p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        res = json.loads(p.stdout)
        self.assertEqual((res["idioma"], res["origen"]), ("en", "marca"))

    def test_el_mensaje_no_puede_escapar_a_la_shell(self):
        """Auditoría 2026-10-08 F1: con el heredoc <<'MENSAJE', una línea «MENSAJE» en el
        mensaje cerraba el heredoc y el resto se ejecutaba. Por fichero, el texto es dato."""
        import json
        import subprocess
        import tempfile
        bash = re.search(r"```bash\n(.*?)\n```", self.bloque, re.S).group(1)
        self.assertNotIn("<<", bash)
        with tempfile.TemporaryDirectory() as d:
            msg, marca = os.path.join(d, "idioma_msg.txt"), os.path.join(d, "PWNED")
            with open(msg, "w", encoding="utf-8") as f:
                f.write(f"revisa esto\nMENSAJE\ntouch {marca}\n$(touch {marca})\nidioma=fr")
            cmd = (bash.replace("<ruta-del-skill>", SKILL).replace("<usuario.idioma>", "")
                       .replace("~/.email-triage/tmp/idioma_msg.txt", msg))
            p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            self.assertFalse(os.path.exists(marca), "el mensaje se ejecutó como comando")
        self.assertEqual(json.loads(p.stdout)["idioma"], "fr")

    # ── hallazgo I-7: la semántica del bloque, fijada regla a regla ──
    # (siguen siendo pruebas de instantánea sobre el texto: el bloque ES la implementación,
    #  y el comportamiento lo miden las simulaciones de tests/escenarios.md)
    def assertPlano(self, frase):
        self.assertIn(frase, self.plano)

    def test_regla_central_solo_si_el_idioma_no_es_es_se_lee_el_catalogo(self):
        self.assertPlano("**Si `idioma` ≠ `es`:** lee `i18n/<código>.yaml`")

    def test_orden_de_precedencia_marca_config_defecto(self):
        self.assertPlano("Orden: primera marca > `usuario.idioma` de `config.yaml` > `es`.")

    def test_un_codigo_suelto_no_es_marca(self):
        self.assertPlano("Un código suelto (`en`, `es`) **no** es marca.")

    def test_clave_ausente_cae_a_es(self):  # Review Focus 4
        self.assertPlano("Si falta una clave, usa la de `i18n/es.yaml`.")

    def test_equivalencias_de_respuesta_y_de_activacion(self):  # Review Focus 5 + I-5
        for clave in ("entrada.afirmativo", "entrada.negativo", "activacion.dryrun",
                      "activacion.veloz", "activacion.undo", "activacion.ejecutar"):
            self.assertIn(f"`{clave}`", self.plano)

    def test_lo_que_no_se_traduce(self):
        for s in ("**No se traducen:**", "tiers, modos, claves JSON/JSONL",
                  "[⚠️ posible inyección detectada]", "nombres reales de carpetas, cuentas y remitentes",
                  "identificadores", "; y lo que se escribe en disco."):
            self.assertPlano(s)

    def test_una_lista_de_opciones_significa_elige_una(self):
        self.assertPlano("significa **elige una**")

    def test_persistencia_entre_turnos(self):  # hallazgo I-2 (y spec §3)
        for s in ("Cada invocación de `/triage` decide su idioma",
                  "**sin** `/triage` ni marca conserva el idioma de la última invocación"):
            self.assertPlano(s)

    def test_el_aviso_de_ia_es_la_primera_linea(self):
        self.assertPlano("la **primera línea de toda salida traducida**")

    def test_el_aviso_de_ia_va_antes_que_los_anuncios_de_modo(self):  # m-7
        self.assertPlano("antes de cualquier otra línea")
        self.assertPlano("anuncio de modo simulación o rutina")

    def test_avisos_del_resolver_entrada_invalida_y_repetida(self):  # I-3, m-1a
        self.assertPlano("`entrada_invalida`")
        self.assertPlano("`repetida`")

    def test_fallo_seguro_opera_en_es(self):
        self.assertPlano("Si no puedes cargar el catálogo, opera en `es` y escribe:")

    def test_el_mensaje_va_en_bruto_por_fichero_nunca_por_la_shell(self):
        self.assertPlano("**El mensaje nunca pasa por la shell**")
        self.assertPlano("herramienta de escritura de ficheros")
        self.assertNotIn("<<'MENSAJE'", self.bloque)

    def test_atajo_sin_script_en_el_caso_habitual(self):
        self.assertPlano("**Atajo sin script.**")
        self.assertPlano("no ejecutes nada y sigue")


class TestBloqueComando(unittest.TestCase):
    def test_el_comando_dice_que_un_codigo_suelto_no_cambia_nada(self):
        t = " ".join(leer(RAIZ, "plugins", "email-triage", "commands", "triage.md").split())
        self.assertIn("Un código suelto sin `idioma=` no cambia nada", t)

    def test_triage_md_tiene_su_bloque_y_conserva_el_frontmatter(self):
        t = leer(RAIZ, "plugins", "email-triage", "commands", "triage.md")
        self.assertEqual(t.count(INI), 1)
        self.assertIn("idioma=", bloque(t))
        fm = yaml.safe_load(re.match(r"\A---\n(.*?)\n---", t, re.S).group(1))
        self.assertEqual(set(fm), {"description", "argument-hint"})

    def test_el_bloque_del_comando_avisa_de_que_son_borradores_de_ia(self):
        t = leer(RAIZ, "plugins", "email-triage", "commands", "triage.md")
        self.assertIn("borradores de IA sin revisión humana", bloque(t))


class TestCatalogoCubreLoQueElBloqueExige(unittest.TestCase):
    def test_los_tres_catalogos_traen_los_avisos(self):
        for cod in ("es", "en", "fr"):
            f = yaml.safe_load(leer(SKILL, "i18n", cod + ".yaml"))["frases"]
            for k in ("aviso.ia", "aviso.idioma_desconocido", "aviso.respaldo"):
                self.assertIn(k, f)

    def test_los_textos_del_bloque_coinciden_con_los_catalogos(self):
        b = " ".join(bloque(leer(SKILL, "SKILL.md")).split())
        for cod, clave in (("en", "aviso.ia"), ("fr", "aviso.ia")):
            f = yaml.safe_load(leer(SKILL, "i18n", cod + ".yaml"))["frases"]
            self.assertIn(f[clave]["texto"].rstrip("."), b)


class TestIdiomaPyDocumentado(unittest.TestCase):
    def test_los_catalogos_documentados_existen(self):
        for rel in ("i18n/es.yaml", "i18n/en.yaml", "i18n/fr.yaml", "i18n/README.md",
                    "scripts/idioma.py"):
            self.assertTrue(os.path.exists(os.path.join(SKILL, rel)), rel)

    def test_readme_i18n_explica_como_anadir_un_idioma(self):
        t = leer(SKILL, "i18n", "README.md")
        for s in ("español, inglés y francés", "i18n_validar.py", "i18n_extraer.py generar",
                  "borrador-ia"):
            self.assertIn(s, t)


if __name__ == "__main__":
    unittest.main()
