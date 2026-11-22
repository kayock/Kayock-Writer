"""Release staging checks: disposable, localhost-only copies of Kayock Writer.

These checks never run an installer against HOME or an installed application.
Linux checks the real optional install helper with an explicit temp destination.
Windows checks the portable copied-source launch (no Windows installer exists).
All files and processes are confined to per-test TemporaryDirectories.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
IS_LINUX = sys.platform.startswith("linux")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage_portable(source, destination):
    destination.mkdir(parents=True)
    for name in ("kayock_writer.py", "config.example.json", "README.md", "LICENSE_NOTES.md"):
        shutil.copy2(source / name, destination / name)
    shutil.copytree(
        source / "app", destination / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
    )


def choose_local_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def verify_copied_source_launch(staged, isolated_data, config):
    """Launch the staged entrypoint with no model or private data access."""
    port = choose_local_port()
    arguments = [
        sys.executable, "-u", "kayock_writer.py",
        "--config", str(config),
        "--data-dir", str(isolated_data),
        "--host", "127.0.0.1",
        "--port", str(port),
        "--base-url", "http://127.0.0.1:1",
        "--model", "synthetic-offline-model"
    ]
    env = dict(os.environ)
    env.pop("KAYOCK_MODEL_API_KEY", None)
    for key in list(env):
        if key.startswith("KAYOCK_WRITER_") or key.startswith("KAYOCK_MODEL_"):
            env.pop(key, None)
    process = subprocess.Popen(
        arguments, cwd=staged, env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )
    try:
        result = None
        for _ in range(90):
            if process.poll() is not None:
                detail = process.stderr.read().decode("utf-8", "replace")[:1600]
                raise AssertionError(
                    "Staged source exited before serving HTTP: " + detail
                )
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:%d/" % port, timeout=0.5
                ) as response:
                    body = response.read().decode("utf-8")
                    if response.status == 200 and "Kayock Writer" in body:
                        result = body
                        break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.1)
        if result is None:
            raise AssertionError("Staged source never served a local Writer homepage.")
        assert "Editorial Council" in result, "Staged UI lacks development Council"
        assert "Controlled Revision Workspace" in result, "Staged UI lacks revisions"
        with urllib.request.urlopen(
            "http://127.0.0.1:%d/api/writer/story/projects" % port, timeout=4
        ) as response:
            payload = json.load(response)
        assert payload["ok"] is True, payload
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


class CleanStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kayock-stage-")
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_portable_source_launch_windows_and_linux(self):
        staged = self.base / "copied-source"
        stage_portable(SRC, staged)
        # Confirm the Python import resolves inside the copied installation,
        # never the checked-out source tree.
        check = subprocess.run(
            [sys.executable, "-c", "import app;print(app.__file__)"],
            cwd=staged, capture_output=True, text=True, timeout=10, check=True
        )
        self.assertTrue(
            Path(check.stdout.strip()).resolve().is_relative_to(staged.resolve()),
            check.stdout
        )
        fixture = staged / "config.json"
        original_config = b'{"unrelated_fixture_setting": "do not overwrite"}\n'
        fixture.write_bytes(original_config)
        self.assertEqual(digest(fixture), hashlib.sha256(original_config).hexdigest())
        target_data = self.base / "test-data"
        verify_copied_source_launch(staged, target_data, fixture)
        self.assertEqual(fixture.read_bytes(), original_config)

    @unittest.skipUnless(IS_LINUX, "Linux helper does not apply to Windows")
    def test_linux_installer_preserves_config_custom_files_and_manuscripts(self):
        dest = self.base / "existing-install"
        dest.mkdir()
        private = dest / "custom-addon.txt"
        config = dest / "config.json"
        draft = dest / "KayockWriterData" / "Projects" / "Fixture" / "chapter.md"
        draft.parent.mkdir(parents=True)
        private.write_bytes(b"author owned addon - leave alone\n")
        config.write_bytes(b'{"model": {"timeout_seconds": 420}}\n')
        draft.write_bytes(b"Original writer manuscript. Do not edit!\n")
        before = {p: digest(p) for p in (private, config, draft)}
        env = dict(os.environ)
        env["KAYOCK_WRITER_INSTALL_DIR"] = str(dest)
        env["PYTHON"] = sys.executable
        # Explicit temp destination; no sudo, service or production path.
        for _ in range(2):
            completed = subprocess.run(
                ["bash", str(SRC / "deploy" / "install-linux.sh")],
                cwd=SRC, env=env, capture_output=True, text=True, timeout=40
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("No processes or services have been touched", completed.stdout)
        for path, hexdigest in before.items():
            self.assertEqual(digest(path), hexdigest, "Installer changed " + str(path))
        self.assertTrue((dest / "app" / "server.py").is_file())
        self.assertTrue((dest / "tests" / "test_revision_workspace.py").is_file())
        verify_copied_source_launch(dest, self.base / "new-test-data", config)

    @unittest.skipUnless(IS_LINUX, "Symlink path check is tested on Linux")
    def test_installer_refuses_symlink_destination_without_writing_target(self):
        target = self.base / "unrelated-target"
        target.mkdir()
        sentinel = target / "keep.txt"
        sentinel.write_bytes(b"keep")
        link = self.base / "linked-install"
        link.symlink_to(target, target_is_directory=True)
        env = dict(os.environ)
        env["KAYOCK_WRITER_INSTALL_DIR"] = str(link)
        env["PYTHON"] = sys.executable
        run = subprocess.run(
            ["bash", str(SRC / "deploy" / "install-linux.sh")],
            cwd=SRC, env=env, capture_output=True, text=True, timeout=20
        )
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("symlink", run.stdout + run.stderr)
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["keep.txt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
