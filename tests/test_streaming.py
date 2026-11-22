"""End-to-end streaming/cancellation tests using local mock HTTP servers only.

No live writer data, paid API, background model, or external network needed.
"""
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
from app.server import serve
from tests.mock_provider import start_mock_server


def sse_events(response):
    name = ""
    data = []
    while True:
        raw = response.readline()
        if not raw:
            if name and data:
                yield name, json.loads("\n".join(data))
            return
        line = raw.decode("utf-8").rstrip("\r\n")
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
        elif not line:
            if name and data:
                yield name, json.loads("\n".join(data))
            name, data = "", []


class StreamingHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = start_mock_server("127.0.0.1", 0)
        cls.model_url = "http://127.0.0.1:" + str(cls.mock.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.mock.shutdown()
        cls.mock.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                     path=Path(self.tmp.name) / "config.json")
        cfg.set("paths.data_dir", str(Path(self.tmp.name) / "data"))
        cfg.set("server.host", "127.0.0.1")
        cfg.set("server.port", 0)
        cfg.set("model.base_url", self.model_url)
        self.writer = serve(cfg)
        self.thread = threading.Thread(target=self.writer.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.writer.server_address[1])

    def tearDown(self):
        self.writer.shutdown()
        self.writer.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.url + path, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        return urllib.request.urlopen(req, timeout=12)

    def _payload(self, direction="Respect the author's work"):
        return {"text": "The lantern passed from hand to hand.\n\nNo one spoke.",
                "title": "Lantern", "writing_type": "prose", "mode": "review",
                "direction": direction}

    def test_streaming_end_to_end_and_no_file_writes(self):
        with self._post("/api/writer/editorial/stream", self._payload()) as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(response.headers["Content-Type"].startswith("text/event-stream"))
            events = list(sse_events(response))
        self.assertEqual(events[0][0], "start")
        self.assertTrue(events[0][1]["generation_id"])
        text = "".join(body["text"] for name, body in events if name == "token")
        self.assertTrue(text.strip())
        self.assertEqual(events[-1][0], "done", events)
        self.assertFalse(events[-1][1]["saved"])
        self.assertTrue(events[-1][1]["source_unchanged"])
        self.assertFalse(list((Path(self.tmp.name) / "data").rglob("*.md")))

    def test_cancel_closes_stream_and_keeps_partial_text_unsaved(self):
        with self._post("/api/writer/editorial/stream",
                        self._payload("SLOW_STREAM_TEST")) as response:
            events = sse_events(response)
            start, info = next(events)
            self.assertEqual(start, "start")
            self.assertEqual(next(events)[0], "token")
            generation_id = info["generation_id"]
            with self._post("/api/generation/" + generation_id + "/cancel", {}) as cancel:
                acknowledgement = json.load(cancel)
            self.assertTrue(acknowledgement["cancelled"])
            tail = list(events)
            self.assertTrue(any(name == "cancelled" for name, _ in tail), tail)
            self.assertFalse(any(name == "done" for name, _ in tail), tail)
            with self._post("/api/generation/" + generation_id + "/cancel", {}) as cancel:
                self.assertFalse(json.load(cancel)["ok"])
        self.assertFalse(list((Path(self.tmp.name) / "data").rglob("*.md")))

    def test_non_sse_endpoint_reports_error_without_fake_success(self):
        with self._post("/api/writer/editorial/stream",
                        self._payload("NO_SSE_TEST")) as response:
            events = list(sse_events(response))
        self.assertEqual(events[0][0], "start")
        self.assertEqual(events[-1][0], "error", events)
        self.assertFalse(any(name == "done" for name, _ in events))

    def test_invalid_editorial_payload_rejected_before_stream(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self._post("/api/writer/editorial/stream", {"text": ""})
        self.assertEqual(raised.exception.code, 400)
        self.assertIn("passage", json.loads(raised.exception.read().decode())["message"])

    def test_classic_editorial_endpoint_remains_compatible(self):
        with self._post("/api/writer/editorial/review", self._payload()) as response:
            result = json.load(response)
        self.assertTrue(result["ok"])
        self.assertFalse(result["saved"])
        self.assertTrue(result["source_unchanged"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
