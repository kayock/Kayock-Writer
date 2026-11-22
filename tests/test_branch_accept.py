"""Explicit acceptance of branch drafts as new, never overwritten canonical versions."""
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
from app.storage import Store,jwrite
from app.storyforge import StoryForge
from app.draft_branches import DraftBranches
from app.config import Config,DEFAULT_CONFIG
from app.server import serve
from app.ui import render_page


def seeded(store):
    root=store.folder("projects")/"StoryProject"
    root.mkdir(parents=True,exist_ok=True)
    jwrite(root/"project.kayock-writer.json",{
        "project_id":"StoryProject","title":"Story Project",
        "books":[{"id":"book_1","title":"Book 1"}]
    })
    forge=StoryForge(store)
    source=forge.draft_save_action({
        "project_id":"StoryProject","book_id":"book_1",
        "chapter":"Chapter One",
        "content":"A bell rang across the hills.",
        "execute":True
    })
    assert source.get("ok"),source
    branches=DraftBranches(store,forge)
    branch=branches.create("StoryProject","book_1",Path(source["path"]).name,
                           "Darker ending")
    assert branch.get("ok"),branch
    read=branches.read("StoryProject","book_1",branch["branch_id"])
    changed=branches.append("StoryProject","book_1",branch["branch_id"],
                            "A bell cracked.\nThe town fell silent.",read["revision"])
    assert changed.get("ok"),changed
    return root,forge,branches,Path(source["path"]),branch["branch_id"]


class AcceptanceUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        (self.root,self.forge,self.branches,
         self.canonical,self.branch_id)=seeded(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def preview(self):
        return self.branches.preview_accept(
            "StoryProject","book_1",self.branch_id)

    def accept(self,token):
        return self.branches.accept(
            "StoryProject","book_1",self.branch_id,token)

    def test_preview_never_writes_accept_appends_only(self):
        previous=self.canonical.read_bytes()
        history=self.root/"Drafts"/"book_1"/"draft_manifest.json"
        original_manifest=history.read_bytes()
        branch_manifest=self.root/"Branches"/"book_1"/self.branch_id/"branch.json"
        branch_bytes=branch_manifest.read_bytes()
        preview=self.preview()
        self.assertTrue(preview["read_only"])
        self.assertTrue(preview["canonical_unchanged"])
        self.assertEqual(preview["expected_next_version"],2)
        self.assertTrue(any("town fell silent" in x for x in preview["diff_preview"]))
        self.assertEqual(previous,self.canonical.read_bytes())
        self.assertEqual(original_manifest,history.read_bytes())
        done=self.accept(preview["confirmation_token"])
        self.assertTrue(done["ok"])
        self.assertTrue(done["accepted"])
        self.assertTrue(done["original_versions_preserved"])
        self.assertTrue(done["branch_preserved"])
        self.assertEqual(done["canonical_version"],2)
        self.assertNotEqual(done["canonical_path"],str(self.canonical))
        self.assertEqual(self.canonical.read_bytes(),previous)
        self.assertEqual(branch_manifest.read_bytes(),branch_bytes)
        result=json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(len(result["versions"]),2)
        self.assertEqual(result["versions"][0]["version"],1)
        self.assertEqual(result["versions"][1]["version"],2)
        self.assertIn("town fell silent",Path(done["canonical_path"]).read_text(encoding="utf-8"))

    def test_stale_branch_preview_rejected(self):
        preview=self.preview()
        read=self.branches.read("StoryProject","book_1",self.branch_id)
        self.branches.append("StoryProject","book_1",self.branch_id,
                             "A fresh alternate ending.",read["revision"])
        before=self.canonical.read_bytes()
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.accept(preview["confirmation_token"])
        self.assertEqual(self.canonical.read_bytes(),before)
        self.assertEqual(len(self.forge._load_draft_manifest("StoryProject","book_1")["versions"]),1)

    def test_stale_main_draft_preview_rejected(self):
        preview=self.preview()
        later=self.forge.draft_save_action({
            "project_id":"StoryProject","book_id":"book_1",
            "chapter":"Chapter One",
            "content":"The author wrote a new canonical version.",
            "execute":True
        })
        self.assertTrue(later["ok"])
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.accept(preview["confirmation_token"])
        self.assertEqual(len(self.forge._load_draft_manifest("StoryProject","book_1")["versions"]),2)

    def test_missing_token_and_second_use_do_not_duplicate(self):
        preview=self.preview()
        with self.assertRaisesRegex(ValueError,"Preview"):
            self.accept("")
        self.accept(preview["confirmation_token"])
        with self.assertRaises(ValueError):
            self.accept(preview["confirmation_token"])
        self.assertEqual(len(self.forge._load_draft_manifest("StoryProject","book_1")["versions"]),2)

    def test_filename_collision_does_not_overwrite_untracked_writing(self):
        preview=self.preview()
        collision=self.root/"Drafts"/"book_1"/"chapter_Chapter_One_draft_v002.md"
        # Existing Story Forge slugging lowercases the chapter name.
        collision=self.root/"Drafts"/"book_1"/"chapter_chapter_one_draft_v002.md"
        collision.write_text("This is unrelated author writing.",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"already exists"):
            self.accept(preview["confirmation_token"])
        self.assertEqual(collision.read_text(encoding="utf-8"),"This is unrelated author writing.")
        self.assertEqual(len(self.forge._load_draft_manifest("StoryProject","book_1")["versions"]),1)


class AcceptanceHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                   path=Path(self.tmp.name)/"config.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writer"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        store=Store(cfg.data_dir())
        (self.root,_,_,self.canonical,self.branch_id)=seeded(store)
        self.server=serve(cfg)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        self.thread.join(timeout=3);self.tmp.cleanup()

    def post(self,path,data):
        req=urllib.request.Request(
            self.base+path,data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=12) as response:return json.load(response)

    def test_preview_and_accept_through_api(self):
        params={"project_id":"StoryProject","book_id":"book_1",
                "branch_id":self.branch_id}
        preview=self.post("/api/writer/story/branches/preview_accept",params)
        self.assertEqual(preview["current_version"],1)
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/writer/story/branches/accept",params)
        result=self.post("/api/writer/story/branches/accept",{
            **params,"confirmation_token":preview["confirmation_token"]})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["canonical_version"],2)
        for marker in ("storyBranchAcceptancePreview","storyBranchAccept",
                       "storyBranchAcceptStatus"):
            self.assertIn(marker,render_page())

    def test_same_preview_cannot_be_accepted_twice_concurrently(self):
        params={"project_id":"StoryProject","book_id":"book_1",
                "branch_id":self.branch_id}
        preview=self.post("/api/writer/story/branches/preview_accept",params)
        payload={**params,"confirmation_token":preview["confirmation_token"]}
        barrier=threading.Barrier(2)
        outcomes=[]
        def worker():
            barrier.wait(timeout=5)
            try:
                response=self.post("/api/writer/story/branches/accept",payload)
                outcomes.append("accepted" if response["accepted"] else "error")
            except urllib.error.HTTPError as exc:
                outcomes.append("rejected" if exc.code==400 else "error")
        a=threading.Thread(target=worker,daemon=True)
        b=threading.Thread(target=worker,daemon=True)
        a.start();b.start();a.join(timeout=12);b.join(timeout=12)
        self.assertEqual(sorted(outcomes),["accepted","rejected"])
        self.assertEqual(len(
            self.server.RequestHandlerClass.app.storyforge._load_draft_manifest(
                "StoryProject","book_1")["versions"]),2)


if __name__=="__main__":
    unittest.main(verbosity=2)
