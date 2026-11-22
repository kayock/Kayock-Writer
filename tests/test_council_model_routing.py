"""Role-specific saved-profile routing and author decision-board safety.

All inference traffic goes to in-process mock endpoints. Tests verify model
dispatch, never changing active config, no credentials leaked to a different
endpoint, and no manuscript/canon files written.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.config import Config,DEFAULT_CONFIG
from app.provider import Provider
from app.storage import Store
from app.model_profiles import ModelProfiles
from app.editorial_council import (
    prepare_council, resolve_council_models, _fingerprint
)
from app.server import serve
from app.ui import render_page
from tests.mock_provider import start_mock_server
from tests.test_streaming import sse_events

TEXT="It was a quiet harbor. The old lighthouse was empty."
BASE={"text":TEXT,"title":"Lighthouse",
      "writing_type":"prose","direction":"Protect the slow pacing.",
      "roles":["story_architect","voice_guardian"]}


def settings(endpoint,model="other-writer",timeout=10011):
    return {"base_url":endpoint,"model":model,
            "chat_path":"/v1/chat/completions",
            "health_path":"/health","health_kind":"auto",
            "timeout_seconds":timeout}


class AlternateMockHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_POST(self):
        payload=json.loads(self.rfile.read(
            int(self.headers.get("Content-Length","0"))).decode("utf-8"))
        self.server.received.append({
            "path":self.path,
            "authorization":self.headers.get("Authorization"),
            "model":payload.get("model"),
            "messages":payload.get("messages"),
            "max_tokens":payload.get("max_tokens"),
        })
        assert self.path=="/v1/chat/completions"
        assert payload.get("stream") is True
        phrase="Notes from independently selected model."
        self.send_response(200)
        self.send_header("Content-Type","text/event-stream; charset=utf-8")
        self.end_headers()
        self.wfile.write(("data: "+json.dumps({"choices":[
            {"delta":{"content":phrase},"finish_reason":None}]})+"\n\n").encode())
        self.wfile.write(("data: "+json.dumps({"choices":[
            {"delta":{},"finish_reason":"stop"}]})+"\n\n").encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


class RoutingUnits(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)))
        cfg.set("model.base_url","http://127.0.0.1:8177")
        cfg.set("model.model","active-writer")
        cfg.set("model.timeout_seconds",30000)
        cfg.set("model.api_key","SECRET-ONLY-FOR-ACTIVE")
        self.config=cfg
        self.active=Provider(cfg)
        self.profiles=ModelProfiles(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_role_choices_use_saved_profiles_and_preserve_timeouts(self):
        other=self.profiles.save("Other Model",settings("http://127.0.0.1:9998"))
        selected=other["profile"]["id"]
        payload={**BASE,"role_profiles":{"voice_guardian":selected}}
        plan=prepare_council(payload,max_tokens=16384)
        models,labels=resolve_council_models(plan,self.active,self.profiles)
        self.assertIs(models["story_architect"],self.active)
        self.assertIsNot(models["voice_guardian"],self.active)
        self.assertEqual(models["voice_guardian"].model_name(),"other-writer")
        self.assertEqual(models["voice_guardian"].base_url(),"http://127.0.0.1:9998")
        self.assertEqual(models["voice_guardian"].timeout(),10011)
        self.assertEqual(self.active.timeout(),30000)
        self.assertEqual(self.active.model_name(),"active-writer")
        self.assertEqual(models["voice_guardian"].cfg.api_key(),"")
        self.assertIn("Other Model",labels["voice_guardian"])
        self.assertEqual(plan["max_tokens"],16384)

    def test_never_forward_env_key_across_endpoint_but_same_endpoint_keeps_it(self):
        different=self.profiles.save("Different",settings("http://127.0.0.1:9990"))
        same=self.profiles.save("Same",settings("http://127.0.0.1:8177",model="alternate-id"))
        with patch.dict(os.environ,{"KAYOCK_MODEL_API_KEY":"ENV-ACTIVE-SECRET"}):
            plan=prepare_council({
                **BASE,"role_profiles":{
                    "story_architect":different["profile"]["id"],
                    "voice_guardian":same["profile"]["id"]
                }
            },max_tokens=4000)
            resolved,_=resolve_council_models(plan,self.active,self.profiles)
            self.assertEqual(resolved["story_architect"].cfg.api_key(),"")
            self.assertEqual(resolved["voice_guardian"].cfg.api_key(),
                             "ENV-ACTIVE-SECRET")
            self.assertEqual(self.active.cfg.api_key(),"ENV-ACTIVE-SECRET")
        self.assertEqual(self.active.cfg.get("model.base_url"),"http://127.0.0.1:8177")

    def test_invalid_unknown_unselected_and_missing_profiles_rejected(self):
        for selection in (
            {"not_a_role":"a"*32},
            {"line_editor":"a"*32},
            {"voice_guardian":"not-a-saved-profile"},
            {"voice_guardian":None},
        ):
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError):
                    prepare_council({**BASE,"role_profiles":selection},
                                    max_tokens=4000)
        for profile in ("missing","bad uuid",42,False):
            with self.assertRaises(ValueError):
                prepare_council({**BASE,"synthesis_profile_id":profile},max_tokens=4000)
        good=prepare_council({
            **BASE,"role_profiles":{"story_architect":"a"*32}
        },max_tokens=4000)
        with self.assertRaisesRegex(ValueError,"missing"):
            resolve_council_models(good,self.active,self.profiles)

    def test_model_assignment_change_invalidates_synthesis_fingerprint(self):
        second=self.profiles.save("Another",settings("http://127.0.0.1:9981"))
        original=prepare_council(dict(BASE),max_tokens=4000)
        reports=[
            {"role":role,"text":"A complete report."} for role in BASE["roles"]
        ]
        changed={**BASE,"stage":"synthesis","reports":reports,
                 "source_fingerprint":original["source_fingerprint"],
                 "role_profiles":{"voice_guardian":second["profile"]["id"]}}
        with self.assertRaisesRegex(ValueError,"changed"):
            prepare_council(changed,max_tokens=4000)
        changed2={**BASE,"stage":"synthesis","reports":reports,
                  "source_fingerprint":original["source_fingerprint"],
                  "synthesis_profile_id":second["profile"]["id"]}
        with self.assertRaisesRegex(ValueError,"changed"):
            prepare_council(changed2,max_tokens=4000)
        self.assertNotEqual(_fingerprint(BASE,BASE["roles"]),
                            _fingerprint(changed,BASE["roles"]))


class RoutingHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.active_mock=start_mock_server("127.0.0.1",0)
        cls.active_url="http://127.0.0.1:"+str(cls.active_mock.server_address[1])
        cls.alternate=ThreadingHTTPServer(("127.0.0.1",0),AlternateMockHandler)
        cls.alternate.daemon_threads=True
        cls.alternate.received=[]
        cls.alternate_url="http://127.0.0.1:"+str(cls.alternate.server_address[1])
        cls.model_thread=threading.Thread(target=cls.alternate.serve_forever,daemon=True)
        cls.model_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.active_mock.shutdown();cls.active_mock.server_close()
        cls.alternate.shutdown();cls.alternate.server_close()
        cls.model_thread.join(timeout=4)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                   path=Path(self.tmp.name)/"config.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writer"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        cfg.set("model.base_url",self.active_url)
        cfg.set("model.model","main-model")
        cfg.set("model.api_key","DO-NOT-FORWARD-THIS")
        cfg.set("model.timeout_seconds",12011)
        cfg.set("writing.editorial_max_tokens",8192)
        self.server=serve(cfg)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])
        self.alternate.received.clear()

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        self.thread.join(timeout=4);self.tmp.cleanup()

    def get(self,path):
        with urllib.request.urlopen(self.base+path,timeout=10) as r:
            return json.load(r)

    def post(self,path,data):
        req=urllib.request.Request(self.base+path,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        return urllib.request.urlopen(req,timeout=15)

    def save_profile(self):
        with self.post("/api/model/profiles/save",{
            "name":"Second Endpoint",
            "settings":settings(self.alternate_url,"alternate-model",7001)
        }) as r:
            return json.load(r)["profile"]["id"]

    def test_live_two_endpoints_and_separate_synthesis_selection(self):
        old_config=self.get("/api/config")["config"]
        selection=self.save_profile()
        req={**BASE,"role_profiles":{"voice_guardian":selection},
             "synthesis_profile_id":selection}
        with self.post("/api/writer/council/stream",req) as r:
            events=list(sse_events(r))
        self.assertEqual(events[-1][0],"done",events)
        starts=[d for n,d in events if n=="role_start"]
        self.assertEqual(len(starts),2)
        self.assertIn("Active: main-model",starts[0]["model"])
        self.assertIn("Second Endpoint",starts[1]["model"])
        self.assertEqual(len(self.alternate.received),1)
        sent=self.alternate.received[0]
        self.assertIsNone(sent["authorization"])
        self.assertEqual(sent["model"],"alternate-model")
        self.assertEqual(sent["max_tokens"],8192)
        self.assertIn(TEXT,sent["messages"][1]["content"])
        reports=[{"role":d["role"],"text":d["text"]}
                 for n,d in events if n=="role_done"]
        synth={**req,"stage":"synthesis","reports":reports,
               "source_fingerprint":events[-1][1]["source_fingerprint"]}
        with self.post("/api/writer/council/stream",synth) as r:
            new=list(sse_events(r))
        self.assertEqual(new[-1][0],"done",new)
        self.assertEqual(len(self.alternate.received),2)
        self.assertIn("COMPLETE, AUTHOR-SUPPLIED COUNCIL REPORTS",
                      self.alternate.received[1]["messages"][1]["content"])
        self.assertIsNone(self.alternate.received[1]["authorization"])
        after=self.get("/api/config")["config"]
        self.assertEqual(after,old_config)
        root=Path(self.tmp.name)/"writer"
        self.assertEqual(list(root.rglob("*.md")),[])
        self.assertEqual(list(root.rglob("*draft_manifest*")),[])

    def test_unknown_profile_http400_before_any_model_inference(self):
        invalid={**BASE,"role_profiles":{"story_architect":"a"*32}}
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post("/api/writer/council/stream",invalid)
        self.assertEqual(err.exception.code,400)
        self.assertEqual(self.alternate.received,[])

    def test_ui_has_separate_role_profile_and_decision_controls(self):
        page=render_page()
        for marker in (
            "councilModelStory","councilModelVoice","councilModelLine",
            "councilModelContinuity","councilModelSynthesis",
            "councilLoadModels()","councilSelectedProfileIds()",
            "councilDecisionBoard","councilDecisionCapture(",
            "councilDecisionExport()","councilDecisionManual()",
            "Approved for consideration","Rejected","Defer",
        ):
            self.assertIn(marker,page)


if __name__=="__main__":
    unittest.main(verbosity=2)
