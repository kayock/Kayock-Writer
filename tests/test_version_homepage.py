"""Version reporting and homepage/metadata checks for Kayock Writer v2.0.0."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import __version__, APP_NAME
from app.config import Config, DEFAULT_CONFIG
from app.server import serve
from app.ui import render_page
from tests.mock_provider import start_mock_server


class VersionHomepageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = start_mock_server("127.0.0.1", 0)
        cls.base = "http://127.0.0.1:" + str(cls.mock.server_address[1])
        cls.tmp = tempfile.TemporaryDirectory(prefix="kayock_version_")
        data = json.loads(json.dumps(DEFAULT_CONFIG))
        data["model"]["base_url"] = cls.base
        data["server"]["host"] = "127.0.0.1"
        data["server"]["port"] = 0
        data["paths"]["data_dir"] = str(Path(cls.tmp.name) / "data")
        cls.cfg = Config(data, path=Path(cls.tmp.name) / "config.json")
        cls.server = serve(cls.cfg)
        cls.host, cls.port = cls.server.server_address[:2]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        try:
            cls.mock.shutdown()
            cls.mock.server_close()
        except Exception:
            pass
        cls.tmp.cleanup()

    def test_central_version_constant(self):
        self.assertEqual(__version__, "2.0.0")
        self.assertEqual(APP_NAME, "Kayock Writer")

    def test_status_reports_version(self):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/api/status", timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["version"], "2.0.0")
        self.assertEqual(payload["app"], "Kayock Writer")

    def test_homepage_represents_v2_capabilities(self):
        html = render_page()
        self.assertIn("Kayock Writer", html)
        self.assertIn("AI-Assisted Creative Writing Studio", html)
        self.assertIn("Editorial &amp; Craft Handoff", html)
        self.assertIn("Editorial Council", html)
        self.assertIn("Author Decision Board", html)
        self.assertIn("Controlled Revision Workspace", html)
        self.assertIn("Full-Book Assembly", html)
        self.assertIn("DOCX", html)
        self.assertIn("EPUB", html)
        self.assertIn("PDF", html)
        self.assertIn('id="cfgSelectionMode"', html)
        self.assertIn("ollama_active", html)
        self.assertIn('id="cfgDisableThinking"', html)
        self.assertNotIn("Release-v1.1.0", html)
        # Navigation remains present for desktop and narrow layouts.
        self.assertIn('id="burger"', html)
        self.assertIn('id="tree"', html)
        self.assertIn("Writer Home", html)
        self.assertIn("Open Finishing Desk", html)


if __name__ == "__main__":
    unittest.main()
