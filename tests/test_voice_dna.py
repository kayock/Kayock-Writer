"""Opt-in private Voice DNA cards and non-destructive editorial modes."""
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
from app.config import Config,DEFAULT_CONFIG
from app.editorial import prepare_editorial
from app.server import serve
from app.storage import Store
from app.ui import render_page
from app.voice_dna import VoiceDNA

SAMPLE="A glass sky bent over the road. The road remembered its old name."
CARD={
    "name":"My voice","author":"A. Writer",
    "traits":["Direct emotion","Unusual short sentences"],
    "preserve":["The ending's final pause"],
    "avoid":["Flattening dialogue"],
    "samples":[SAMPLE]
}

class VoiceUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        self.library=VoiceDNA(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_list_read_and_explicit_context(self):
        created=self.library.create(dict(CARD))
        self.assertTrue(created["ok"])
        listed=self.library.list()
        self.assertIsNone(listed["active_profile"])
        self.assertTrue(listed["opt_in_required"])
        self.assertNotIn(SAMPLE,json.dumps(listed))
        info=self.library.get(created["profile_id"])
        self.assertEqual(info["profile"]["samples"],[SAMPLE])
        context=self.library.prompt_context(created["profile_id"])
        self.assertIn(SAMPLE,context)
        self.assertIn("do not",context.lower())
        self.assertNotIn("API key",context)

    def test_invalid_sample_duplicate_corruption_and_delete_backup(self):
        created=self.library.create(dict(CARD))
        with self.assertRaisesRegex(ValueError,"already exists"):
            self.library.create(dict(CARD))
        with self.assertRaises(ValueError):
            self.library.create({**CARD,"samples":["x"*2001]})
        with self.assertRaises(ValueError):
            self.library.create({**CARD,"new_setting":"secret"})
        removed=self.library.delete(created["profile_id"])
        self.assertTrue(removed["ok"])
        self.assertEqual(self.library.list()["profiles"],[])
        backup=list(self.store.folder("backups").glob("voice_dna/profiles_*.json"))
        self.assertTrue(backup)
        self.assertIn(SAMPLE,backup[0].read_text(encoding="utf-8"))
        self.library.create(dict(CARD))
        file=self.library._path()
        file.write_text("{invalid",encoding="utf-8")
        before=file.read_bytes()
        with self.assertRaisesRegex(ValueError,"damaged"):
            self.library.create(dict(CARD))
        self.assertEqual(file.read_bytes(),before)

    def test_developmental_and_voice_audit_do_not_change_base_review(self):
        for mode in ("review","developmental","voice_audit","suggestion"):
            prepared=prepare_editorial({"text":"A cliff rose.","mode":mode})
            self.assertTrue(prepared["ok"])
            self.assertIn("A cliff rose.",prepared["messages"][1]["content"])
        self.assertIn("STRENGTHS",prepare_editorial(
            {"text":"A cliff rose.","mode":"review"})["messages"][0]["content"])
        self.assertIn("STRUCTURAL STRENGTHS",prepare_editorial(
            {"text":"A cliff rose.","mode":"developmental"})["messages"][0]["content"])
        self.assertIn("DISTINCTIVE VOICE",prepare_editorial(
            {"text":"A cliff rose.","mode":"voice_audit"})["messages"][0]["content"])
        self.assertFalse(prepare_editorial(
            {"text":"A cliff rose.","mode":"made_up"})["ok"])

class VoiceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(self.tmp.name)/"cfg.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writer"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        cfg.set("model.model","unchanged-model")
        cfg.set("model.timeout_seconds",420)
        self.server=serve(cfg)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])
        self.provider=self.server.RequestHandlerClass.app.provider
        self.messages=[]
        def fake_chat(messages, *,max_tokens,temperature):
            self.messages.append((messages,max_tokens,temperature))
            return {"ok":True,"text":"Review notes. Do not rewrite the author."}
        def fake_stream(messages, *,max_tokens,temperature,cancellation):
            self.messages.append((messages,max_tokens,temperature))
            yield {"type":"token","text":"Streamed notes."}
            yield {"type":"done"}
        self.provider.chat=fake_chat
        self.provider.stream_chat=fake_stream

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        self.thread.join(timeout=3);self.tmp.cleanup()

    def post(self,path,payload):
        req=urllib.request.Request(
            self.base+path,data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=10) as r:
            if path.endswith("/stream"):
                return r.read().decode("utf-8")
            return json.load(r)

    def get(self,path):
        with urllib.request.urlopen(self.base+path,timeout=10) as r:return json.load(r)

    def test_opt_in_and_off_by_default_for_classic_and_streamed(self):
        new=self.post("/api/writer/voice_dna/create",{"profile":CARD})
        self.assertTrue(new["ok"])
        identifier=new["profile_id"]
        listed=self.get("/api/writer/voice_dna")
        self.assertNotIn(SAMPLE,json.dumps(listed))
        read=self.get("/api/writer/voice_dna/read?id="+identifier)
        self.assertEqual(read["profile"]["samples"],[SAMPLE])
        standard={"text":"The road was quiet.","mode":"voice_audit",
                  "writing_type":"prose"}
        response=self.post("/api/writer/editorial/review",standard)
        self.assertTrue(response["ok"])
        self.assertNotIn(SAMPLE,self.messages[-1][0][0]["content"])
        self.assertEqual(self.messages[-1][1],4000)
        self.assertEqual(self.server.RequestHandlerClass.app.cfg.get(
            "model.timeout_seconds"),420)
        selected={**standard,"use_voice_dna":True,"voice_dna_id":identifier}
        response=self.post("/api/writer/editorial/review",selected)
        self.assertTrue(response["source_unchanged"])
        self.assertIn(SAMPLE,self.messages[-1][0][0]["content"])
        streamed=self.post("/api/writer/editorial/stream",selected)
        self.assertIn("event: done",streamed)
        self.assertIn(SAMPLE,self.messages[-1][0][0]["content"])
        self.assertEqual(self.server.RequestHandlerClass.app.cfg.get(
            "model.model"),"unchanged-model")
        self.assertEqual(list((Path(self.tmp.name)/"writer").rglob("*.md")),[])

    def test_bad_opt_in_does_not_reach_model_and_ui_is_explicit(self):
        with self.assertRaises(urllib.error.HTTPError) as exc:
            self.post("/api/writer/editorial/review",{
                "text":"Author's original draft.",
                "use_voice_dna":True,
                "voice_dna_id":"nonexistent"})
        self.assertEqual(exc.exception.code,400)
        self.assertEqual(self.messages,[])
        for marker in ("finishUseVoiceDna","finishVoiceDnaSelect",
                       "voiceDnaCreate()","voiceDnaInspect()",
                       "voiceDnaDelete()","developmental","voice_audit"):
            self.assertIn(marker,render_page())


if __name__=="__main__":
    unittest.main(verbosity=2)
