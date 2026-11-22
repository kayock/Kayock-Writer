"""Canon HTTP regression tests for human-controlled Story Bible decisions."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Config, DEFAULT_CONFIG
from app.server import serve
from app.ui import render_page


class CanonHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "writing"
        cfg = Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                     path=Path(self.tmp.name) / "config.json")
        cfg.set("paths.data_dir", str(self.data))
        cfg.set("server.host", "127.0.0.1")
        cfg.set("server.port", 0)
        self.writer = serve(cfg)
        self.thread = threading.Thread(target=self.writer.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.writer.server_address[1])
        self.assertTrue(self.post("/api/novelforge/save", {
            "universe": "Test Universe", "premise": "An isolated regression test.",
            "characters": ["Elena"]
        })["ok"])

    def tearDown(self):
        self.writer.shutdown()
        self.writer.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def post(self, path, payload):
        req = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as response:
            return json.load(response)

    def proposed(self):
        return {
            "universe": "Test_Universe", "kind": "character",
            "subject": "Elena", "claim": "Her scar is on her left arm.",
            "source": "Book 1, Chapter 3", "quote": "She touched the scar on her left arm.",
            "chapter": "03", "world_time": "Day 4",
            "narrative_order": "Book 1, Chapter 3"
        }

    def test_http_approval_never_overwrites_existing_universe(self):
        original = self.data / "NovelForge" / "Test_Universe.json"
        before = original.read_bytes()
        proposal = self.post("/api/novelforge/canon/propose", self.proposed())
        self.assertTrue(proposal["ok"])
        fact_id = proposal["fact"]["id"]
        facts = self.get("/api/novelforge/canon?name=Test_Universe")["facts"]
        self.assertEqual(facts[0]["state"], "proposed")
        self.assertEqual(facts[0]["world_time"], "Day 4")
        self.assertEqual(facts[0]["evidence"][0]["source"], "Book 1, Chapter 3")
        approved = self.post("/api/novelforge/canon/review", {
            "universe": "Test_Universe", "fact_id": fact_id, "decision": "approved"})
        self.assertEqual(approved["fact"]["state"], "approved")
        self.assertEqual(original.read_bytes(), before)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/api/novelforge/canon/review", {
                "universe": "Test_Universe", "fact_id": fact_id, "decision": "rejected"})
        self.assertEqual(error.exception.code, 400)

    def test_missing_source_or_unknown_universe_is_rejected(self):
        d = self.proposed()
        d["quote"] = ""
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/api/novelforge/canon/propose", d)
        self.assertEqual(error.exception.code, 400)
        d = self.proposed()
        d["universe"] = "Not_Created"
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/api/novelforge/canon/propose", d)
        self.assertEqual(error.exception.code, 400)

    def test_rename_moves_canon_and_preserves_approved_facts(self):
        proposal = self.post("/api/novelforge/canon/propose", self.proposed())
        self.post("/api/novelforge/canon/review", {
            "universe": "Test_Universe", "fact_id": proposal["fact"]["id"],
            "decision": "approved"})
        renamed = self.post("/api/novelforge/rename", {
            "name": "Test_Universe", "new_title": "Renamed Universe"})
        self.assertTrue(renamed["ok"], renamed)
        facts = self.get("/api/novelforge/canon?name=Renamed_Universe")["facts"]
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["state"], "approved")
        self.assertFalse((self.data / "NovelForge" / ".canon" / "Test_Universe").exists())

    def test_delete_retains_separate_canon_review_history(self):
        self.post("/api/novelforge/canon/propose", self.proposed())
        deleted = self.post("/api/novelforge/delete", {"name": "Test_Universe"})
        self.assertTrue(deleted["ok"])
        self.assertTrue(deleted["canon_retained"])
        self.assertTrue((self.data / "NovelForge" / ".canon" /
                         "Test_Universe" / "facts.json").is_file())

    def test_browser_has_approval_controls_and_read_only_editor(self):
        html = render_page()
        for marker in ("nfCanonList", "proposeCanonFact()", "reviewCanonFact(",
                       "nfCanonQuote", "nfCanonWorldTime", "finishStop",
                       "finishingReviewClassic()", "finishingCancel()"):
            self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
