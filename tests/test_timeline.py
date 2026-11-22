"""Time-aware continuity and explicit character knowledge regression tests."""
from __future__ import annotations
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.timeline import parse_world_time, chronology, character_knowledge
from app.continuity import check
from app.config import Config, DEFAULT_CONFIG
from app.server import serve


def record(key, claim, time="", known_by=None, learned_time="", state="approved"):
    return {
        "id": key, "kind": "character", "subject": "Elena",
        "claim": claim, "world_time": time, "narrative_order": "Chapter " + key,
        "known_by": known_by if known_by is not None else [],
        "learned_time": learned_time, "state": state,
        "evidence": [{"source": "Chapter " + key, "quote": claim}],
    }


class TimelineUnitTests(unittest.TestCase):
    def setUp(self):
        self.facts=[
            record("one", "Elena is alive.", "Day 1", ["Marcus"], "Day 3"),
            record("two", "Elena is dead.", "Day 5", ["Marcus"], "Day 7"),
            record("pending", "Elena has a scar on her left arm.", "Day 3",
                   ["Marcus"], "Day 3", "proposed"),
            record("calendar", "Elena has a scar on her right arm.",
                   "2030-02-01", ["Marcus"], "2030-02-02"),
            record("undated", "Elena is dead.", "Ancient Era",
                   ["Marcus"], ""),
        ]

    def test_world_time_parser_only_orders_compatible_and_valid_labels(self):
        self.assertEqual(parse_world_time("Day 15"), ("day",15))
        self.assertEqual(parse_world_time("day 02"), ("day",2))
        self.assertIsNone(parse_world_time("Ancient Era"))
        self.assertIsNone(parse_world_time("2030-02-30"))
        self.assertIsNone(parse_world_time("Book 1 Chapter 3"))
        self.assertEqual(parse_world_time("2030-01-01")[0],"date")

    def test_chronology_groups_days_and_calendar_dates_without_guessing(self):
        view=chronology(self.facts)
        self.assertEqual(view["total"],4)
        self.assertEqual([group["time_system"] for group in view["groups"]],["day","date"])
        self.assertEqual([f["id"] for f in view["groups"][0]["facts"]],["one","two"])
        self.assertEqual(view["unplaced"][0]["id"],"undated")
        self.assertNotIn("pending",json.dumps(view))

    def test_later_approved_state_supersedes_earlier_one_at_selected_day(self):
        early=check("Elena is alive.",self.facts,world_time="Day 2")
        late=check("Elena is dead.",self.facts,world_time="Day 6")
        self.assertEqual(early["alert_count"],0)
        self.assertEqual(late["alert_count"],0)
        self.assertTrue(late["time_scope_applied"])
        self.assertEqual(late["future_facts_excluded"],0)
        self.assertGreaterEqual(late["undated_or_incomparable_facts_excluded"],2)
        self.assertEqual(check("Elena is dead.",self.facts,world_time="Day 2")["alert_count"],1)
        self.assertEqual(check("Elena is alive.",self.facts,world_time="Day 6")["alert_count"],1)

    def test_unrecognized_time_rejected_not_silently_sorted(self):
        with self.assertRaises(ValueError):
            check("Elena is dead.",self.facts,world_time="Ancient Era")
        self.assertFalse(check("Elena is dead.",self.facts)["time_scope_applied"])

    def test_knowledge_uses_declared_learning_time_not_world_event_time(self):
        at_day4=character_knowledge(self.facts,"Marcus","Day 4")
        self.assertEqual([f["id"] for f in at_day4["facts"]],["one"])
        self.assertEqual(at_day4["later_known_facts_excluded"],1)
        self.assertEqual(len(at_day4["time_uncertain_facts"]),2)
        at_day8=character_knowledge(self.facts,"Marcus","Day 8")
        self.assertEqual([f["id"] for f in at_day8["facts"]],["one","two"])
        self.assertFalse(any(f["id"]=="pending" for f in at_day8["facts"]))
        self.assertEqual(character_knowledge(self.facts,"Elena","Day 8")["count"],0)
        with self.assertRaises(ValueError):
            character_knowledge(self.facts,"Marcus","Book 2")

    def test_unknown_learning_time_not_assumed_known_at_specific_day(self):
        f=[record("a","Elena is alive.","Day 1",["Marcus"],"")]
        result=character_knowledge(f,"Marcus","Day 4")
        self.assertEqual(result["facts"],[])
        self.assertEqual(len(result["time_uncertain_facts"]),1)


class TimelineHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(self.tmp.name)/"config.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writing"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        self.writer=serve(cfg)
        self.thread=threading.Thread(target=self.writer.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.writer.server_address[1])
        self.post("/api/novelforge/save",{"universe":"World","premise":"Test story"})

    def tearDown(self):
        self.writer.shutdown()
        self.writer.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def post(self,path,data):
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode(),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=10) as response:
            return json.load(response)

    def propose(self,claim,time,learned):
        data=self.post("/api/novelforge/canon/propose",{
            "universe":"World","kind":"character","subject":"Elena",
            "claim":claim,"source":"Chapter 1","quote":claim,
            "world_time":time,"narrative_order":"Chapter 1",
            "known_by":["Marcus","Marcus"],"learned_time":learned,
        })
        self.post("/api/novelforge/canon/review",{
            "universe":"World","fact_id":data["fact"]["id"],"decision":"approved"
        })
        return data["fact"]["id"]

    def test_timeline_knowledge_and_time_specific_review_never_change_universe(self):
        self.propose("Elena is alive.", "Day 1", "Day 2")
        self.propose("Elena is dead.", "Day 5", "Day 7")
        path=Path(self.tmp.name)/"writing"/"NovelForge"/"World.json"
        before=path.read_bytes()
        timeline=self.post("/api/novelforge/canon/chronology",{"universe":"World"})
        self.assertEqual(timeline["total"],2)
        knowledge=self.post("/api/novelforge/canon/knowledge",{
            "universe":"World","character":"Marcus","at_world_time":"Day 3"
        })
        self.assertEqual(knowledge["count"],1)
        self.assertEqual(knowledge["later_known_facts_excluded"],1)
        check_result=self.post("/api/novelforge/canon/continuity",{
            "universe":"World","text":"Elena is alive.","world_time":"Day 6"
        })
        self.assertEqual(check_result["alert_count"],1)
        self.assertEqual(check_result["alerts"][0]["approved_claim"],"Elena is dead.")
        self.assertEqual(path.read_bytes(),before)

    def test_knowledge_rejects_nonlist_known_by_and_unsupported_time(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("/api/novelforge/canon/propose",{
                "universe":"World","kind":"character","subject":"Elena",
                "claim":"Elena is alive.","source":"Chapter 1",
                "quote":"Elena is alive.","known_by":"all"
            })
        self.assertEqual(error.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/novelforge/canon/knowledge",{
                "universe":"World","character":"Marcus",
                "at_world_time":"Some era"
            })


if __name__=="__main__":
    unittest.main(verbosity=2)
