"""Editorial Council v2: independent advisory roles, explicit synthesis, SSE/cancel.

All tests run against an in-process model stub or the repo's local mock HTTP
model. Never touches actual writing, paid endpoints, model configs or files.
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

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.config import Config, DEFAULT_CONFIG
from app.editorial_council import (
    ROLES, MAX_ROLES, _fingerprint, prepare_council, council_events
)
from app.provider import Cancellation
from app.server import serve
from app.ui import render_page
from tests.mock_provider import start_mock_server
from tests.test_streaming import sse_events

PASSAGE="A worn lantern moved through the crowd.\n\nNo one dared speak."
REQUEST={
    "title":"The Lantern","writing_type":"prose",
    "direction":"Protect the author's ending.",
    "text":PASSAGE,
    "roles":["story_architect","voice_guardian"]
}


class FakeProvider:
    def __init__(self, trigger_cancel=None, outcome="ok"):
        self.calls=[]
        self.trigger_cancel=trigger_cancel
        self.outcome=outcome

    def stream_chat(self,messages,*,max_tokens,temperature,cancellation):
        self.calls.append({"messages":messages,"max_tokens":max_tokens,
                           "temperature":temperature})
        role=messages[0]["content"].split("ROLE: ",1)[-1].split(".",1)[0]
        yield {"type":"token","text":"Review from "+role+". Exact draft: "}
        yield {"type":"token","text":PASSAGE}
        if self.outcome=="error":
            yield {"type":"error","message":"Model failed."}
        elif self.outcome=="unfinished":
            return
        else:
            if self.trigger_cancel is not None and len(self.calls)==self.trigger_cancel:
                cancellation.cancel()
                yield {"type":"cancelled"}
                return
            yield {"type":"done"}


class CouncilUnitTests(unittest.TestCase):
    def test_plan_has_exact_source_in_each_independent_role(self):
        plan=prepare_council(dict(REQUEST),max_tokens=12000)
        self.assertEqual(plan["call_count"],2)
        self.assertEqual(plan["max_tokens"],12000)
        self.assertFalse(plan["saved"])
        model=FakeProvider()
        events=list(council_events(model,plan,Cancellation()))
        self.assertEqual([e for e,_ in events].count("role_start"),2)
        self.assertEqual([e for e,_ in events].count("role_done"),2)
        self.assertEqual(events[-1][0],"done")
        self.assertEqual([i["role"] for name,i in events if name=="role_done"],
                         REQUEST["roles"])
        self.assertEqual(len(model.calls),2)
        for call in model.calls:
            self.assertIn(PASSAGE,call["messages"][1]["content"])
            self.assertNotIn("Review from",call["messages"][1]["content"])
            self.assertNotIn("Voice DNA REFERENCE",call["messages"][0]["content"])
            self.assertNotIn("APPROVED CANON REFERENCE",call["messages"][0]["content"])
            self.assertEqual(call["max_tokens"],12000)
            self.assertEqual(call["temperature"],0.35)
        self.assertIn("ROLE: Story Architect",model.calls[0]["messages"][0]["content"])
        self.assertIn("ROLE: Voice Guardian",model.calls[1]["messages"][0]["content"])

    def test_opted_in_context_only_when_passed_by_author(self):
        params={**REQUEST,"use_canon":True,"use_voice_dna":True}
        plan=prepare_council(params,max_tokens=4000,
            canon_context="Approved: lighthouse remains dark.",
            voice_context="Style: preserve abrupt punctuation.")
        for item in plan["work"]:
            self.assertIn("lighthouse remains dark",item["messages"][0]["content"])
            self.assertIn("abrupt punctuation",item["messages"][0]["content"])
        default=prepare_council(dict(REQUEST),max_tokens=4000)
        self.assertNotIn("lighthouse",json.dumps(default))
        self.assertNotIn("abrupt punctuation",json.dumps(default))

    def test_bad_roles_and_text_rejected_before_model_call(self):
        variants=[
            {**REQUEST,"roles":[]},
            {**REQUEST,"roles":["story_architect"]*2},
            {**REQUEST,"roles":list(ROLES)},
            {**REQUEST,"roles":["unknown"]},
            {**REQUEST,"roles":["story_architect",None]},
            {**REQUEST,"text":""},
            {**REQUEST,"text":"a"*80001},
            {**REQUEST,"stage":"auto_apply"},
        ]
        for payload in variants:
            with self.subTest(roles=payload.get("roles"),stage=payload.get("stage")):
                with self.assertRaises(ValueError):
                    prepare_council(payload,max_tokens=4000)
        self.assertEqual(MAX_ROLES,3)

    def test_synthesis_is_separate_call_uses_all_reports_unshortened(self):
        provider=FakeProvider()
        plan=prepare_council(dict(REQUEST),max_tokens=4000)
        reports=[{"role":item["role"],"text":item["text"]}
                 for event,item in council_events(provider,plan,Cancellation())
                 if event=="role_done"]
        self.assertEqual(len(provider.calls),2)
        synth_input={**REQUEST,"stage":"synthesis","reports":reports,
                     "source_fingerprint":plan["source_fingerprint"]}
        synthesis=prepare_council(synth_input,max_tokens=16000)
        self.assertEqual(synthesis["call_count"],1)
        message=synthesis["work"][0]["messages"][1]["content"]
        self.assertIn(PASSAGE,message)
        for result in reports:
            self.assertIn(result["text"],message)
        self.assertNotIn("compacted",message.lower())
        finished=list(council_events(provider,synthesis,Cancellation()))
        self.assertEqual(len(provider.calls),3)
        self.assertEqual([event for event,_ in finished].count("role_done"),1)
        self.assertEqual(finished[-1][0],"done")
        self.assertEqual(provider.calls[-1]["max_tokens"],16000)

    def test_no_implicit_synthesis_invalid_report_sets_rejected(self):
        base=prepare_council(dict(REQUEST),max_tokens=4000)
        reports=[{"role":"story_architect","text":"A complete report"},
                 {"role":"voice_guardian","text":"Other full report"}]
        good={**REQUEST,"stage":"synthesis","reports":reports,
              "source_fingerprint":base["source_fingerprint"]}
        variants=[
            {**good,"source_fingerprint":"bad"},
            {**good,"reports":reports[:1]},
            {**good,"reports":list(reversed(reports))},
            {**good,"reports":[reports[0],{"role":"voice_guardian","text":""}]},
            {**good,"reports":[reports[0],{"role":"voice_guardian","text":"A"*120001}]},
            {**good,"text":"The author edited the passage."},
            {**good,"roles":["continuity_editor","voice_guardian"]},
        ]
        for payload in variants:
            with self.subTest(payload=str(payload)[:120]):
                with self.assertRaises(ValueError):
                    prepare_council(payload,max_tokens=4000)

    def test_cancel_mid_run_never_calls_second_role(self):
        provider=FakeProvider(trigger_cancel=1)
        plan=prepare_council(dict(REQUEST),max_tokens=4000)
        token=Cancellation()
        events=list(council_events(provider,plan,token))
        self.assertEqual([e for e,_ in events][-1],"cancelled")
        self.assertEqual(len(provider.calls),1)
        self.assertFalse(any(e=="done" for e,_ in events))

    def test_unfinished_or_failed_stream_stops_no_next_model_call(self):
        for outcome in ("error","unfinished"):
            provider=FakeProvider(outcome=outcome)
            plan=prepare_council(dict(REQUEST),max_tokens=4000)
            events=list(council_events(provider,plan,Cancellation()))
            self.assertEqual(events[-1][0],"error")
            self.assertEqual(len(provider.calls),1)
            self.assertFalse(any(e=="done" for e,_ in events))


class CouncilHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock=start_mock_server("127.0.0.1",0)
        cls.model_url="http://127.0.0.1:"+str(cls.mock.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.mock.shutdown()
        cls.mock.server_close()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                   path=Path(self.tmp.name)/"config.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"data"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        cfg.set("model.base_url",self.model_url)
        cfg.set("model.timeout_seconds",420)
        cfg.set("writing.editorial_max_tokens",11000)
        self.writer=serve(cfg)
        self.thread=threading.Thread(target=self.writer.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:"+str(self.writer.server_address[1])

    def tearDown(self):
        self.writer.shutdown()
        self.writer.server_close()
        self.thread.join(timeout=4)
        self.tmp.cleanup()

    def post(self,path,payload):
        req=urllib.request.Request(self.url+path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        return urllib.request.urlopen(req,timeout=25)

    def get(self,path):
        with urllib.request.urlopen(self.url+path,timeout=8) as resp:
            return json.load(resp)

    def assert_no_manuscript_writes(self):
        root=Path(self.tmp.name)/"data"
        self.assertFalse(list(root.rglob("*.md")))
        self.assertFalse(list(root.rglob("*.json")))

    def test_roles_discovery_and_full_two_role_stream(self):
        advertised=self.get("/api/writer/council/roles")
        self.assertEqual(advertised["max_roles"],3)
        self.assertFalse(advertised["automatic_synthesis"])
        self.assertEqual({x["id"] for x in advertised["roles"]},set(ROLES))
        with self.post("/api/writer/council/stream",REQUEST) as stream:
            self.assertIn("text/event-stream",stream.headers["Content-Type"])
            events=list(sse_events(stream))
        self.assertEqual(events[0][0],"start")
        self.assertEqual(events[0][1]["call_count"],2)
        self.assertEqual([event for event,_ in events].count("role_start"),2)
        self.assertEqual([event for event,_ in events].count("role_done"),2)
        self.assertEqual(events[-1][0],"done",events)
        self.assertFalse(events[-1][1]["saved"])
        self.assertTrue(events[-1][1]["source_unchanged"])
        reports=[{"role":body["role"],"text":body["text"]}
                 for event,body in events if event=="role_done"]
        synth={**REQUEST,"stage":"synthesis","reports":reports,
               "source_fingerprint":events[-1][1]["source_fingerprint"]}
        with self.post("/api/writer/council/stream",synth) as stream:
            next_events=list(sse_events(stream))
        self.assertEqual(next_events[0][1]["call_count"],1)
        self.assertEqual([x["role"] for event,x in next_events
                          if event=="role_start"],["synthesis"])
        self.assertEqual(next_events[-1][0],"done")
        self.assert_no_manuscript_writes()
        self.assertEqual(self.writer.RequestHandlerClass.app.cfg.get(
            "model.timeout_seconds"),420)
        self.assertEqual(self.writer.RequestHandlerClass.app.cfg.get(
            "writing.editorial_max_tokens"),11000)

    def test_invalid_or_stale_synthesis_is_http400_without_stream(self):
        for payload in (
            {**REQUEST,"roles":[]},
            {**REQUEST,"stage":"synthesis","reports":[],"source_fingerprint":"bad"},
            {**REQUEST,"text":""},
        ):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.post("/api/writer/council/stream",payload)
            self.assertEqual(raised.exception.code,400)
        self.assert_no_manuscript_writes()

    def test_cancellation_stops_next_role(self):
        payload={**REQUEST,"direction":"SLOW_STREAM_TEST"}
        with self.post("/api/writer/council/stream",payload) as response:
            events=sse_events(response)
            event,start=next(events)
            self.assertEqual(event,"start")
            generation_id=start["generation_id"]
            self.assertEqual(next(events)[0],"role_start")
            self.assertEqual(next(events)[0],"role_token")
            with self.post("/api/generation/"+generation_id+"/cancel",{}) as control:
                data=json.load(control)
            self.assertTrue(data["cancelled"])
            tail=list(events)
            self.assertEqual(tail[-1][0],"cancelled",tail)
            self.assertFalse(any(name=="done" for name,_ in tail))
            self.assertFalse(any(name=="role_start" and data["role"]=="voice_guardian"
                                 for name,data in tail))
        self.assert_no_manuscript_writes()

    def test_ui_has_explicit_approval_buttons_and_read_only_outputs(self):
        html=render_page()
        for piece in (
            "Editorial Council","councilRun()","councilStop()",
            "councilSynthesize()","councilReports","councilLive",
            "councilSummary","councilState.reviewComplete","1–3"
        ):
            self.assertIn(piece,html)
        self.assertIn('id="councilSummary" class="big" readonly',html)
        self.assertIn('id="councilSynthesizeButton" onclick="councilSynthesize()" disabled',html)


if __name__=="__main__":
    unittest.main(verbosity=2)
