"""Ollama active selection and disable_thinking — no live model load/unload."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Config, DEFAULT_CONFIG
from app.provider import Provider
from tests.mock_provider import MockHandler, start_mock_server


class OllamaActiveSelectionTests(unittest.TestCase):
    def setUp(self):
        self.MockHandler = MockHandler
        MockHandler.loaded_models = [{"name": "alpha:1", "model": "alpha:1"}]
        MockHandler.last_chat_payload = None
        self.server = start_mock_server("127.0.0.1", 0)
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])
        self.tmp = tempfile.TemporaryDirectory(prefix="kayock_active_")
        data = json.loads(json.dumps(DEFAULT_CONFIG))
        data["model"]["base_url"] = self.base
        data["model"]["selection_mode"] = "ollama_active"
        data["model"]["model"] = ""
        data["model"]["disable_thinking"] = True
        self.cfg = Config(data, path=Path(self.tmp.name) / "config.json")
        self.provider = Provider(self.cfg)

    def tearDown(self):
        MockHandler.loaded_models = [{"name": "mock-model", "model": "mock-model"}]
        MockHandler.last_chat_payload = None
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_defaults_remain_fixed_compatible(self):
        fresh = Config(json.loads(json.dumps(DEFAULT_CONFIG)))
        provider = Provider(fresh)
        self.assertEqual(provider.selection_mode(), "fixed")
        resolved = provider.resolve_model()
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["reason"], "fixed")
        self.assertEqual(resolved["model"], "local-model")

    def test_single_loaded_model_is_selected(self):
        resolved = self.provider.resolve_model()
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["model"], "alpha:1")
        self.assertEqual(resolved["reason"], "single_active")

    def test_zero_loaded_models_clear_message(self):
        MockHandler.loaded_models = []
        resolved = self.provider.resolve_model()
        self.assertFalse(resolved["ok"])
        self.assertIn("No model is currently loaded", resolved["message"])

    def test_multiple_loaded_uses_preferred(self):
        MockHandler.loaded_models = [
            {"name": "alpha:1", "model": "alpha:1"},
            {"name": "beta:2", "model": "beta:2"},
        ]
        self.cfg.set("model.model", "beta:2")
        resolved = self.provider.resolve_model()
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["model"], "beta:2")
        self.assertEqual(resolved["reason"], "preferred_among_active")

    def test_multiple_without_preferred_asks_settings(self):
        MockHandler.loaded_models = [
            {"name": "alpha:1", "model": "alpha:1"},
            {"name": "beta:2", "model": "beta:2"},
        ]
        self.cfg.set("model.model", "")
        resolved = self.provider.resolve_model()
        self.assertFalse(resolved["ok"])
        self.assertIn("Multiple models are loaded", resolved["message"])

    def test_chat_uses_active_model_and_disables_thinking(self):
        result = self.provider.chat(
            [{"role": "user", "content": "Reply with: ready"}],
            max_tokens=16, temperature=0.0)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["model_name"], "alpha:1")
        payload = MockHandler.last_chat_payload or {}
        self.assertEqual(payload.get("model"), "alpha:1")
        self.assertIs(payload.get("think"), False)

    def test_stream_uses_active_model_and_disables_thinking(self):
        events = list(self.provider.stream_chat(
            [{"role": "user", "content": "Reply with: ready"}],
            max_tokens=16, temperature=0.0))
        kinds = [e.get("type") for e in events]
        self.assertIn("token", kinds)
        self.assertIn("done", kinds)
        payload = MockHandler.last_chat_payload or {}
        self.assertEqual(payload.get("model"), "alpha:1")
        self.assertIs(payload.get("think"), False)
        self.assertTrue(payload.get("stream"))


if __name__ == "__main__":
    unittest.main()
