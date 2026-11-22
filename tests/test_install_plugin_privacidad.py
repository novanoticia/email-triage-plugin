"""Comprueba el instalador con un HOME temporal y Git sin red."""

import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest


INSTALADOR = Path(__file__).resolve().parents[1] / "scripts" / "install-plugin.sh"
CONFIG_REPO = "plugins/email-triage/skills/email-triage/config.yaml"


class InstaladorPrivadoTest(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.home = Path(temporal.name) / "casa de prueba"
        self.home.mkdir()
        self.estado = self.home / ".email-triage"
        self.config = self.estado / "config.yaml"
        self.repo = self.home / ".claude/plugins/marketplaces/email-triage-plugin"
        self.comandos = self.home / "comandos-git"
        self.bin = self.home / "bin"
        self.bin.mkdir()
        falso = self.bin / "git"
        falso.write_text("#!/usr/bin/env python3\n" + textwrap.dedent('''\
            import os
            from pathlib import Path
            import stat
            import sys

            home = Path.home()
            estado = home / ".email-triage"
            config = estado / "config.yaml"
            args = sys.argv[1:]
            accion = args[2] if args[0] == "-C" else args[0]
            with (home / "comandos-git").open("a") as registro:
                registro.write(accion + "\\n")
            assert stat.S_IMODE(estado.stat().st_mode) == 0o700
            if accion == "diff":
                if os.environ.get("INSTALADOR_ORIGEN_AUSENTE"):
                    (Path(args[1]) / args[-1]).unlink()
                if os.environ.get("INSTALADOR_CONFIG_CONCURRENTE"):
                    config.write_bytes(b"personal concurrente")
                if os.environ.get("INSTALADOR_ERROR_DIFF"):
                    sys.exit(128)
                if os.environ.get("INSTALADOR_SIN_CAMBIOS"):
                    sys.exit(0)
                sys.exit(1)
            if accion == "fetch" and not os.environ.get("INSTALADOR_SIN_CAMBIOS"):
                assert config.is_file()
                if os.environ.get("INSTALADOR_CONFIG_NUEVO"):
                    assert stat.S_IMODE(config.stat().st_mode) == 0o600
            if accion == "reset":
                plantilla = Path(args[1]) / "plugins/email-triage/skills/email-triage/config.yaml"
                plantilla.write_bytes(b"plantilla")
            if accion == "clone":
                repo = Path(args[-1])
                assert not repo.exists()
                (repo / ".git").mkdir(parents=True)
                plantilla = repo / "plugins/email-triage/skills/email-triage/config.yaml"
                plantilla.parent.mkdir(parents=True)
                plantilla.write_bytes(b"plantilla")
                manifiesto = repo / "plugins/email-triage/.claude-plugin/plugin.json"
                manifiesto.parent.mkdir()
                manifiesto.write_text('{"version": "3.28.6"}', encoding="utf-8")
            '''), encoding="utf-8")
        falso.chmod(0o700)

    def preparar_repo(self):
        destino = self.repo / CONFIG_REPO
        destino.parent.mkdir(parents=True)
        destino.write_bytes(b"config v3.3")
        (self.repo / ".git").mkdir()
        manifiesto = self.repo / "plugins/email-triage/.claude-plugin/plugin.json"
        manifiesto.parent.mkdir()
        manifiesto.write_text('{"version": "3.28.6"}', encoding="utf-8")

    def instalar(self, **opciones):
        env = dict(os.environ, HOME=str(self.home),
                   PATH=f"{self.bin}:{Path(sys.executable).parent}:/usr/bin:/bin",
                   **opciones)
        return subprocess.run(["bash", str(INSTALADOR)], env=env, cwd=self.home,
                              capture_output=True, text=True, timeout=15)

    def test_migracion_privada_antes_de_fetch_y_reset(self):
        self.preparar_repo()
        self.estado.mkdir()
        self.estado.chmod(0o755)
        resultado = self.instalar(INSTALADOR_CONFIG_NUEVO="1")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.comandos.read_text().splitlines(), ["diff", "fetch", "reset"])
        self.assertEqual(self.config.read_bytes(), b"config v3.3")
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertEqual(list(self.estado.iterdir()), [self.config])

    def test_instalacion_desde_plantilla(self):
        resultado = self.instalar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.comandos.read_text().splitlines(), ["clone"])
        self.assertEqual(self.config.read_bytes(), b"plantilla")
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)

    def test_actualizacion_sin_personalizaciones_usa_la_plantilla_nueva(self):
        self.preparar_repo()
        resultado = self.instalar(INSTALADOR_SIN_CAMBIOS="1")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.comandos.read_text().splitlines(), ["diff", "fetch", "reset"])
        self.assertEqual(self.config.read_bytes(), b"plantilla")
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)

    def test_preserva_config_existente_o_creado_durante_actualizacion(self):
        self.preparar_repo()
        resultado = self.instalar(INSTALADOR_CONFIG_CONCURRENTE="1")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.config.read_bytes(), b"personal concurrente")

        resultado = self.instalar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.config.read_bytes(), b"personal concurrente")

    def test_directorio_enlace_se_rechaza_antes_de_git(self):
        self.preparar_repo()
        destino = self.home / "otro directorio"
        destino.mkdir()
        destino.chmod(0o755)
        self.estado.symlink_to(destino, target_is_directory=True)

        resultado = self.instalar()
        self.assertNotEqual(resultado.returncode, 0)
        self.assertFalse(self.comandos.exists())
        self.assertEqual(list(destino.iterdir()), [])
        self.assertEqual(stat.S_IMODE(destino.stat().st_mode), 0o755)

    def test_config_enlace_colgante_se_rechaza_antes_de_git(self):
        self.preparar_repo()
        self.estado.mkdir()
        destino = self.home / "config ausente"
        self.config.symlink_to(destino)

        resultado = self.instalar()
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("config.yaml debe ser un archivo regular", resultado.stderr)
        self.assertFalse(self.comandos.exists())
        self.assertFalse(destino.exists())

    def test_error_de_git_diff_interrumpe_antes_de_reset(self):
        self.preparar_repo()
        resultado = self.instalar(INSTALADOR_ERROR_DIFF="1")
        self.assertNotEqual(resultado.returncode, 0)
        self.assertEqual(self.comandos.read_text().splitlines(), ["diff"])
        self.assertEqual((self.repo / CONFIG_REPO).read_bytes(), b"config v3.3")

    def test_error_de_migracion_interrumpe_antes_de_reset(self):
        self.preparar_repo()
        resultado = self.instalar(INSTALADOR_ORIGEN_AUSENTE="1")
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("No se pudo preparar el estado privado", resultado.stderr)
        self.assertEqual(self.comandos.read_text().splitlines(), ["diff"])
        self.assertEqual(list(self.estado.iterdir()), [])

    @unittest.skipUnless(sys.platform == "darwin", "ACL de macOS")
    def test_elimina_acl_del_directorio_de_estado(self):
        self.preparar_repo()
        self.estado.mkdir()
        subprocess.run(["/bin/chmod", "+a", "everyone allow read,search",
                        str(self.estado)], check=True)
        resultado = self.instalar(INSTALADOR_CONFIG_NUEVO="1")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        permisos = subprocess.check_output(["/bin/ls", "-lde", str(self.estado)], text=True)
        self.assertEqual(len(permisos.splitlines()), 1, permisos)
