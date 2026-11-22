"""Tests for approved and evidence-backed relationship graph."""
from __future__ import annotations
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.relationships import build_graph
from app.config import Config, DEFAULT_CONFIG
from app.server import serve
from app.ui import render_page


def fact(key, source, target="", relation="", state="approved"):
    return {"id":key,"kind":"relationship","state":state,
        "subject":source,"related_to":target,"relation_type":relation,
        "claim":source+" trusts "+target,"world_time":"Day 4",
        "narrative_order":"Chapter 2",
        "evidence":[{"source":"Chapter 2","quote":source+" trusts "+target}]}


class RelationshipUnitTests(unittest.TestCase):
    def test_graph_has_only_approved_explicit_links(self):
        records=[fact("a","Elena","Marcus","ally"),
                 fact("b","Elena","Captain","rival"),
                 fact("c","Marcus","Captain","sibling","proposed"),
                 fact("d","Elena","Other","mentor","rejected"),
                 fact("old","Elena")]
        first=build_graph(records)
        self.assertEqual(first,build_graph(records))
        self.assertTrue(first["read_only"])
        self.assertEqual(first["edge_count"],2)
        self.assertEqual(first["unstructured_approved_relationships"],1)
        self.assertEqual({n["name"] for n in first["nodes"]},{"Elena","Marcus","Captain"})
        self.assertEqual(first["edges"][0]["evidence"][0]["source"],"Chapter 2")
        self.assertNotIn("Other",json.dumps(first))
        self.assertEqual(first["edges"][0]["relation_type"],"ally")

    def test_exact_focus_limit_and_inert_strings(self):
        records=[fact("a","Elena","Marcus","ally"),fact("b","Marcus","Zev","rival")]
        self.assertEqual(build_graph(records,focus="ELENA")["edge_count"],1)
        self.assertEqual(build_graph(records,focus="El")["edge_count"],0)
        result=build_graph(records,max_edges=1)
        self.assertEqual(result["matching_edge_total"],2)
        self.assertTrue(result["truncated"])
        for limit in (0,251,True):
            with self.assertRaises(ValueError): build_graph(records,max_edges=limit)
        raw='<img src=x onerror=alert(1)>'
        self.assertEqual(build_graph([fact("X",raw,"Marcus","ally")])["edges"][0]["source_name"],raw)


class RelationshipHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(self.tmp.name)/"cfg.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"data"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        self.writer=serve(cfg)
        self.thread=threading.Thread(target=self.writer.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.writer.server_address[1])
        self.post("/api/novelforge/save",{"universe":"Example world","characters":["Elena","Marcus"]})

    def tearDown(self):
        self.writer.shutdown();self.writer.server_close()
        self.thread.join(timeout=3);self.tmp.cleanup()

    def post(self,path,data):
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode(),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)

    def proposal(self,target="Marcus",relation="ally"):
        return self.post("/api/novelforge/canon/propose",{
            "universe":"Example_world","kind":"relationship","subject":"Elena",
            "related_to":target,"relation_type":relation,
            "claim":"Elena trusts Marcus","source":"Chapter 2",
            "quote":"Elena said she trusted Marcus","world_time":"Day 4"
        })

    def test_only_approved_links_appear_and_source_is_preserved(self):
        novel=Path(self.tmp.name)/"data"/"NovelForge"/"Example_world.json"
        before=novel.read_bytes()
        candidate=self.proposal()
        self.assertTrue(candidate["ok"])
        blank=self.post("/api/novelforge/canon/relationships",{"universe":"Example_world"})
        self.assertEqual(blank["edge_count"],0)
        self.post("/api/novelforge/canon/review",{
            "universe":"Example_world","fact_id":candidate["fact"]["id"],
            "decision":"approved"})
        graph=self.post("/api/novelforge/canon/relationships",{"universe":"Example_world"})
        self.assertEqual(graph["edge_count"],1)
        self.assertEqual(graph["edges"][0]["source_name"],"Elena")
        self.assertEqual(graph["edges"][0]["target_name"],"Marcus")
        self.assertEqual(graph["edges"][0]["evidence"][0]["source"],"Chapter 2")
        self.assertEqual(novel.read_bytes(),before)

    def test_partial_and_self_links_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.proposal(target="Marcus",relation="")
        self.assertEqual(e.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError):
            self.proposal(target="Elena",relation="self")
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/novelforge/canon/propose",{
                "universe":"Example_world","kind":"character","subject":"Elena",
                "related_to":"Marcus","relation_type":"ally",
                "claim":"text","source":"Chapter 1","quote":"text"})

    def test_interface_has_svg_and_evidence(self):
        html=render_page()
        for name in ("Relationship Explorer","renderRelationshipGraph()",
                     "createElementNS","nfGraph","nfCanonRelatedTo","nfCanonRelationType"):
            self.assertIn(name,html)


if __name__=="__main__":
    unittest.main(verbosity=2)
