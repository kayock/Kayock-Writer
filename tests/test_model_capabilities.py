"""Advertised-only model capabilities; no inference is used to inspect them."""
from __future__ import annotations
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.config import Config, DEFAULT_CONFIG
from app.provider import Provider
from app.server import serve
from tests.mock_provider import start_mock_server


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                        path=Path(self.tmp.name)/"config.json")
        self.cfg.set("model.model", "test-id")
        self.provider=Provider(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_declared_metadata_is_not_inferred(self):
        def fake(url, payload, timeout):
            self.assertTrue(url.endswith("/v1/models"))
            self.assertIsNone(payload)
            return True, json.dumps({"data": [
                {"id": "test-id", "context_length": 65536,
                 "capabilities": {"tool_calling": False, "vision": True}},
                {"id": "another-model"}
            ]}), ""
        self.provider._request=fake
        before=json.dumps(self.cfg.data,sort_keys=True)
        result=self.provider.advertised_capabilities()
        self.assertTrue(result["ok"])
        self.assertEqual(result["declared_context_window"],65536)
        self.assertIs(result["declared_tool_calling"],False)
        self.assertIs(result["declared_vision"],True)
        self.assertIsNone(result["declared_streaming"])
        self.assertTrue(result["model_found"])
        self.assertEqual(json.dumps(self.cfg.data,sort_keys=True), before)

    def test_unreported_and_unknown_model_are_unknown(self):
        self.provider._request=lambda url,payload,timeout:(True,json.dumps(
            {"data":[{"id":"test-id"}]}),"")
        result=self.provider.advertised_capabilities()
        for key in ("declared_context_window","declared_tool_calling",
                    "declared_vision","declared_streaming"):
            self.assertIsNone(result[key], key)
        self.cfg.set("model.model","not-in-list")
        result=self.provider.advertised_capabilities()
        self.assertFalse(result["model_found"])
        self.assertIsNone(result["declared_context_window"])
        self.assertEqual(result["advertised_models"],["test-id"])

    def test_bad_endpoint_never_changes_settings_or_loads_model(self):
        self.provider._request=lambda url,payload,timeout:(False,None,"offline")
        self.provider.chat=lambda *args,**kwargs: self.fail("No generation allowed")
        self.assertFalse(self.provider.advertised_capabilities()["ok"])
        self.provider._request=lambda url,payload,timeout:(True,"not JSON","")
        self.assertFalse(self.provider.advertised_capabilities()["ok"])
        self.assertEqual(self.cfg.get("model.timeout_seconds"),420)


class CapabilityHttpTests(unittest.TestCase):
    def test_route_uses_mock_endpoint_without_any_chat_generation(self):
        mock=start_mock_server("127.0.0.1",0)
        try:
            with tempfile.TemporaryDirectory() as directory:
                cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(directory)/"config.json")
                cfg.set("paths.data_dir",str(Path(directory)/"writing"))
                cfg.set("server.host","127.0.0.1")
                cfg.set("server.port",0)
                cfg.set("model.model","mock-model")
                cfg.set("model.base_url","http://127.0.0.1:"+str(mock.server_address[1]))
                writer=serve(cfg)
                writer.RequestHandlerClass.app.provider.chat=lambda *a,**kw: self.fail(
                    "Passive metadata inspection must not use chat")
                thread=threading.Thread(target=writer.serve_forever,daemon=True)
                thread.start()
                try:
                    url="http://127.0.0.1:"+str(writer.server_address[1])+"/api/model/capabilities"
                    with urllib.request.urlopen(url,timeout=5) as response:
                        result=json.load(response)
                    self.assertTrue(result["ok"],result)
                    self.assertTrue(result["model_found"])
                    self.assertIsNone(result["declared_context_window"])
                    self.assertFalse(result["settings_changed"])
                finally:
                    writer.shutdown()
                    writer.server_close()
                    thread.join(timeout=3)
        finally:
            mock.shutdown()
            mock.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
