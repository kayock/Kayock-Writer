"""Offline regression coverage for inert, credential-free model presets."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Config, DEFAULT_CONFIG
from app.model_profiles import ModelProfiles, validate_settings
from app.server import serve
from app.storage import Store
from app.ui import render_page


def preset(**overrides):
    data = {
        "base_url": "http://127.0.0.1:13305",
        "chat_path": "/v1/chat/completions",
        "health_path": "/health",
        "health_kind": "auto",
        "model": "author-local-model",
        "timeout_seconds": 12000,
    }
    data.update(overrides)
    return data


class ProfileUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))
        self.profiles = ModelProfiles(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_read_delete_preserves_exact_model_timeout(self):
        made = self.profiles.save("Long context", preset())
        self.assertTrue(made["ok"])
        self.assertFalse(made["active_changed"])
        self.assertFalse(made["credentials_stored"])
        listed = self.profiles.list()["profiles"]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["settings"], preset())
        self.assertEqual(listed[0]["settings"]["timeout_seconds"], 12000)
        removed = self.profiles.delete(made["profile"]["id"])
        self.assertTrue(removed["ok"])
        self.assertEqual(self.profiles.list()["profiles"], [])
        backups = list(self.store.folder("backups").glob("model_profiles/profiles_*.json"))
        self.assertEqual(len(backups), 1)
        self.assertIn("Long context", backups[0].read_text(encoding="utf-8"))

    def test_duplicate_name_requires_new_name(self):
        self.profiles.save("Author", preset())
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.profiles.save("author", preset(model="another"))

    def test_never_store_keys_or_auth_in_profile(self):
        for value in (
            preset(api_key="secret"),
            preset(base_url="http://username:password@localhost:12345"),
            preset(base_url="http://localhost:12345/?token=secret"),
            preset(extra_option="secret"),
        ):
            with self.assertRaises(ValueError):
                self.profiles.save("Should refuse", value)
        self.assertEqual(self.profiles.list()["profiles"], [])
        self.assertFalse(self.profiles._path().exists())

    def test_invalid_timeout_or_endpoint_never_persists(self):
        for value in (preset(timeout_seconds=0), preset(timeout_seconds=3.14),
                      preset(timeout_seconds="420"), preset(timeout_seconds=True),
                      preset(health_kind="invented"),
                      preset(chat_path="relative/path"),
                      preset(base_url="file:///not-a-model")):
            with self.assertRaises(ValueError):
                validate_settings(value)
        self.assertFalse(self.profiles._path().exists())

    def test_corrupt_data_not_silently_overwritten(self):
        self.profiles.save("Author", preset())
        path = self.profiles._path()
        path.write_text('{"schema":"kayock.writer.model_profiles.v1","profiles":[{"id":"broken","name":"danger","settings":{"api_key":"secret"}}]}',
                        encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.profiles.list()
        with self.assertRaises(ValueError):
            self.profiles.save("After damage", preset())
        self.assertEqual(path.read_bytes(), before)


class ProfileHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                     path=Path(self.tmp.name) / "config.json")
        cfg.set("paths.data_dir", str(Path(self.tmp.name) / "writer"))
        cfg.set("server.host", "127.0.0.1")
        cfg.set("server.port", 0)
        cfg.set("model.api_key", "key-never-in-profiles")
        cfg.set("model.timeout_seconds", 15555)
        cfg.set("model.model", "active-local-model")
        self.writer = serve(cfg)
        self.thread = threading.Thread(target=self.writer.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.writer.server_address[1])

        def no_inference(*args, **kwargs):
            raise AssertionError("Saving profiles must not call a model server.")

        self.writer.RequestHandlerClass.app.provider.chat = no_inference
        self.writer.RequestHandlerClass.app.provider.stream_chat = no_inference
        self.writer.RequestHandlerClass.app.provider._request = no_inference

    def tearDown(self):
        self.writer.shutdown()
        self.writer.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=8) as response:
            return json.load(response)

    def post(self, path, data):
        request = urllib.request.Request(self.base + path,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.load(response)

    def test_http_profile_operations_do_not_activate_or_expose_api_key(self):
        before = self.get("/api/config")["config"]
        self.assertEqual(self.get("/api/model/profiles")["profiles"], [])
        result = self.post("/api/model/profiles/save", {
            "name": "On-demand writer", "settings": preset()
        })
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["active_changed"])
        listed = self.get("/api/model/profiles")["profiles"]
        self.assertEqual(listed[0]["settings"]["timeout_seconds"], 12000)
        self.assertEqual(self.get("/api/config")["config"], before)
        location = Path(self.tmp.name) / "writer" / "Projects" / "KayockWriter" / "ModelProfiles" / "profiles.json"
        saved = location.read_text(encoding="utf-8")
        self.assertNotIn("key-never-in-profiles", saved)
        self.assertNotIn("api_key", saved)
        deleted = self.post("/api/model/profiles/delete", {
            "profile_id": result["profile"]["id"]
        })
        self.assertTrue(deleted["ok"])
        self.assertEqual(self.get("/api/config")["config"], before)

    def test_http_rejects_secret_and_duplicate_profiles(self):
        p = preset()
        p["api_key"] = "not-allowed"
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post("/api/model/profiles/save", {"name": "Secrets", "settings": p})
        self.assertEqual(e.exception.code, 400)
        self.post("/api/model/profiles/save", {"name": "Saved", "settings": preset()})
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post("/api/model/profiles/save", {"name": "Saved", "settings": preset()})
        self.assertEqual(e.exception.code, 400)

    def test_profile_controls_present(self):
        html = render_page()
        for marker in ("cfgProfileSelect", "saveModelProfile()",
                       "stageModelProfile()", "deleteModelProfile()",
                       "cfgProfileName", "Saved Model Profiles"):
            self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
