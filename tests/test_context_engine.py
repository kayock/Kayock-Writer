"""Offline tests for approved Story Bible retrieval, review and opt-in prompting."""
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
from app.context import format_canon_context, preview, rank_approved
from app.continuity import check
from app.server import serve


def fact(fid, subject, claim, state="approved", world_time="Day 3"):
    return {
        "id": fid, "kind": "character", "subject": subject, "claim": claim,
        "state": state, "world_time": world_time,
        "narrative_order": "Book 1 / Chapter 3",
        "evidence": [{"source": "Book 1 Chapter 3", "quote": claim}]
    }


class RetrievalUnitTests(unittest.TestCase):
    def setUp(self):
        self.facts = [
            fact("a", "Elena", "Elena is alive"),
            fact("b", "Marcus", "Marcus is dead"),
            fact("c", "Elena", "Elena has a scar on her left arm", "proposed"),
            fact("d", "Elena", "Elena is dead", "rejected"),
        ]

    def test_relevance_is_deterministic_and_strictly_approved(self):
        a = preview(self.facts, "Elena's rescue", limit=8)
        b = preview(self.facts, "Elena's rescue", limit=8)
        self.assertEqual(a, b)
        self.assertEqual([f["id"] for f in a["facts"]], ["a"])
        self.assertEqual(a["approved_total"], 2)
        self.assertIn("[Fact a]", a["context_text"])
        self.assertNotIn("scar on her left arm", a["context_text"])
        self.assertNotIn("Marcus is dead", a["context_text"])

    def test_zero_match_is_empty_not_unrelated_or_proposed_context(self):
        result = preview(self.facts, "the orange spaceship", 10)
        self.assertEqual(result["selected_total"], 0)
        self.assertEqual(result["context_text"], "")
        self.assertEqual(result["estimated_tokens"], 0)

    def test_empty_query_lists_approved_only_and_limit_is_record_count(self):
        result = preview(self.facts, "", 1)
        self.assertEqual(result["approved_total"], 2)
        self.assertEqual(result["selected_total"], 1)
        self.assertEqual(result["facts"][0]["id"], "a")
        self.assertEqual(len(preview(self.facts, "", 200)["facts"]), 2)

    def test_queries_and_limits_have_explicit_bounds_without_changing_model_context(self):
        for limit in (0, 201, True):
            with self.assertRaises(ValueError):
                rank_approved(self.facts, "Elena", limit)
        with self.assertRaises(ValueError):
            rank_approved(self.facts, "a" * 80001)

    def test_conflict_warning_carries_canon_evidence_and_timing(self):
        result = check("Elena is dead. Marcus is dead.", self.facts)
        self.assertEqual(result["alert_count"], 1)
        alert = result["alerts"][0]
        self.assertEqual(alert["subject"], "Elena")
        self.assertEqual(alert["fact_id"], "a")
        self.assertEqual(alert["world_time"], "Day 3")
        self.assertEqual(alert["draft_value"], "dead")
        self.assertTrue(alert["evidence"])
        self.assertFalse(result["saved"])

    def test_negation_and_unknown_subject_do_not_raise_false_alerts(self):
        self.assertEqual(check("Elena is not dead.", self.facts)["alert_count"], 0)
        self.assertEqual(check("A stranger is dead.", self.facts)["alert_count"], 0)
        self.assertEqual(check("Elena is alive.", self.facts)["alert_count"], 0)

    def test_scar_disagreement_is_advisory_only(self):
        baseline = [fact("scar", "Elena", "Elena has a scar on her left arm")]
        result = check("Elena has a scar on her right arm.", baseline)
        self.assertEqual(result["alert_count"], 1)
        self.assertEqual(result["alerts"][0]["attribute"], "scar:arm")
        self.assertEqual(result["alerts"][0]["severity"], "review")
        self.assertFalse(check("Elena has a scar on her left arm.", baseline)["alerts"])


class ContextHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                     path=Path(self.tmp.name) / "config.json")
        cfg.set("paths.data_dir", str(Path(self.tmp.name) / "writing"))
        cfg.set("server.host", "127.0.0.1")
        cfg.set("server.port", 0)
        self.writer = serve(cfg)
        self.thread = threading.Thread(target=self.writer.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.writer.server_address[1])
        self.post("/api/novelforge/save", {"universe": "Example", "characters": ["Elena"]})

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

    def propose(self, subject="Elena", claim="Elena is alive", approve=True):
        obj = {
            "universe": "Example", "kind": "character", "subject": subject,
            "claim": claim, "source": "Chapter 1", "quote": claim,
            "world_time": "Day 1", "narrative_order": "Chapter 1"
        }
        p = self.post("/api/novelforge/canon/propose", obj)
        if approve:
            self.post("/api/novelforge/canon/review", {
                "universe": "Example", "fact_id": p["fact"]["id"],
                "decision": "approved"
            })
        return p["fact"]["id"]

    def test_context_http_uses_only_approved_and_does_not_touch_universe(self):
        self.propose()
        self.propose("Marcus", "Marcus is dead", False)
        manuscript = Path(self.tmp.name) / "writing" / "NovelForge" / "Example.json"
        before = manuscript.read_bytes()
        result = self.post("/api/novelforge/canon/context", {
            "universe": "Example", "query": "Elena arrives",
            "limit": 15
        })
        self.assertTrue(result["ok"])
        self.assertTrue(result["read_only"])
        self.assertEqual([f["subject"] for f in result["facts"]], ["Elena"])
        self.assertIn("Chapter 1", result["context_text"])
        self.assertEqual(manuscript.read_bytes(), before)

    def test_continuity_http_is_advisory_and_read_only(self):
        self.propose()
        result = self.post("/api/novelforge/canon/continuity", {
            "universe": "Example", "text": "Elena is dead."
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["alert_count"], 1)
        self.assertFalse(result["saved"])
        self.assertTrue(result["source_unchanged"])

    def test_editorial_is_opt_in_both_classic_and_streamed(self):
        self.propose()
        seen = []
        provider = self.writer.RequestHandlerClass.app.provider

        def fake_chat(messages, *, max_tokens, temperature):
            seen.append(("classic", messages[0]["content"], max_tokens))
            return {"ok": True, "text": "A cautious editorial review."}

        def fake_stream(messages, *, max_tokens, temperature, cancellation):
            seen.append(("stream", messages[0]["content"], max_tokens))
            yield {"type": "token", "text": "Streaming review"}
            yield {"type": "done"}

        provider.chat = fake_chat
        provider.stream_chat = fake_stream
        request = {
            "text": "Elena is dead.", "mode": "review", "writing_type": "prose"
        }
        classic = self.post("/api/writer/editorial/review", request)
        self.assertTrue(classic["ok"])
        self.assertNotIn("AUTHOR-APPROVED STORY BIBLE", seen[-1][1])
        request.update({"use_canon": True, "universe": "Example", "canon_limit": 12})
        classic = self.post("/api/writer/editorial/review", request)
        self.assertTrue(classic["ok"])
        self.assertIn("Elena is alive", seen[-1][1])
        self.assertIn("Chapter 1", seen[-1][1])
        self.assertIn("AUTHOR-APPROVED STORY BIBLE", seen[-1][1])
        req = urllib.request.Request(
            self.base + "/api/writer/editorial/stream",
            data=json.dumps(request).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            events = response.read().decode("utf-8")
        self.assertIn("event: done", events)
        self.assertEqual(seen[-1][0], "stream")
        self.assertIn("Elena is alive", seen[-1][1])
        # Editorial endpoints never create draft files or edit the universe.
        self.assertEqual(list((Path(self.tmp.name) / "writing").rglob("Drafts/*.md")), [])

    def test_missing_universe_requires_explicit_selection(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/api/writer/editorial/review", {
                "text": "Elena is alive.", "use_canon": True,
                "writing_type": "prose", "mode": "review"
            })
        self.assertEqual(error.exception.code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
