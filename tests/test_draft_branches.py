"""Offline alternative draft-branch tests: create, append, diff and isolation."""
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


def seed(store):
    root=store.folder("projects")/"Fork_Test"
    root.mkdir(parents=True,exist_ok=True)
    jwrite(root/"project.kayock-writer.json",{
        "project_id":"Fork_Test","title":"Fork Test","books":[
            {"id":"book_1","title":"Book 1"},{"id":"book_2","title":"Book 2"}]
    })
    story=StoryForge(store)
    result=story.draft_save_action({
        "project_id":"Fork_Test","book_id":"book_1",
        "chapter":"Chapter One","content":"The flame shifted.\nThen it rose.",
        "execute":True
    })
    assert result.get("ok"),result
    return story,root,result["path"]


class DraftBranchUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        self.story,self.root,self.original=seed(self.store)
        self.branches=DraftBranches(self.store,self.story)
        self.filename=Path(self.original).name

    def tearDown(self):
        self.tmp.cleanup()

    def create(self,name="Alternate ending"):
        return self.branches.create("Fork_Test","book_1",self.filename,name)

    def test_fork_isolated_from_original_and_can_advance(self):
        source_before=Path(self.original).read_bytes()
        manifest=self.root/"Drafts"/"book_1"/"draft_manifest.json"
        manifest_before=manifest.read_bytes()
        project_before=(self.root/"project.kayock-writer.json").read_bytes()
        fork=self.create()
        self.assertTrue(fork["ok"])
        self.assertEqual(fork["version"],1)
        self.assertEqual(self.branches.list("Fork_Test","book_1")["branches"][0]["versions"],1)
        reading=self.branches.read("Fork_Test","book_1",fork["branch_id"])
        self.assertEqual(reading["content"],"The flame shifted.\nThen it rose.")
        updated="The flame shifted.\nThen the lantern broke.\nThe shore remained dark."
        result=self.branches.append("Fork_Test","book_1",fork["branch_id"],
                                    updated,reading["revision"])
        self.assertTrue(result["canonical_unchanged"])
        self.assertEqual(result["version"],2)
        after=self.branches.read("Fork_Test","book_1",fork["branch_id"])
        self.assertEqual(after["content"],updated)
        diff=self.branches.compare_source("Fork_Test","book_1",fork["branch_id"])
        self.assertTrue(diff["different"])
        self.assertTrue(any("lantern broke" in ln for ln in diff["diff_preview"]))
        self.assertEqual(Path(self.original).read_bytes(),source_before)
        self.assertEqual(manifest.read_bytes(),manifest_before)
        self.assertEqual((self.root/"project.kayock-writer.json").read_bytes(),project_before)
        paths=list((self.root/"Branches"/"book_1"/fork["branch_id"]).glob("*.md"))
        self.assertEqual(len(paths),2)
        self.assertTrue(any("The flame shifted." in p.read_text(encoding="utf-8") for p in paths))
        self.assertEqual(self.branches.list("Fork_Test","book_2")["branches"],[])

    def test_stale_revision_and_duplicate_content_refused(self):
        fork=self.create()
        before=self.branches.read("Fork_Test","book_1",fork["branch_id"])
        with self.assertRaisesRegex(ValueError,"unchanged"):
            self.branches.append("Fork_Test","book_1",fork["branch_id"],
                                 before["content"],before["revision"])
        first=self.branches.append("Fork_Test","book_1",fork["branch_id"],
                                   "Different ending",before["revision"])
        with self.assertRaisesRegex(ValueError,"changed since loading"):
            self.branches.append("Fork_Test","book_1",fork["branch_id"],
                                 "Stale tab",before["revision"])
        self.assertEqual(self.branches.read("Fork_Test","book_1",fork["branch_id"])["revision"],
                         first["revision"])

    def test_invalid_source_foreign_book_and_missing_project_rejected(self):
        for name in ("../private.md","not-a-real-version.md",self.filename.replace(".md",".txt")):
            with self.assertRaises(ValueError):
                self.branches.create("Fork_Test","book_1",name,"Alternative")
        with self.assertRaises(ValueError):
            self.branches.create("Fork_Test","book_2",self.filename,"Wrong book")
        with self.assertRaises(ValueError):
            self.branches.create("Unknown_Project","book_1",self.filename,"Wrong project")
        with self.assertRaises(ValueError):
            self.branches.create("Fork_Test","book_1",self.filename,"")

    def test_damaged_branch_manifest_never_overwritten(self):
        fork=self.create()
        file=self.root/"Branches"/"book_1"/fork["branch_id"]/"branch.json"
        file.write_text("{not valid",encoding="utf-8")
        before=file.read_bytes()
        with self.assertRaisesRegex(ValueError,"damaged"):
            self.branches.read("Fork_Test","book_1",fork["branch_id"])
        with self.assertRaisesRegex(ValueError,"damaged"):
            self.branches.append("Fork_Test","book_1",fork["branch_id"],
                                 "Different", "bad-revision")
        self.assertEqual(file.read_bytes(),before)
        self.assertEqual(self.branches.list("Fork_Test","book_1")["damaged_branches"],1)

    def test_source_external_change_blocks_comparison_not_maintaining_branch(self):
        fork=self.create()
        Path(self.original).write_text("Unexpected external content",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"differs from version history"):
            self.branches.compare_source("Fork_Test","book_1",fork["branch_id"])
        # Existing separately stored branch is still readable, untouched.
        self.assertEqual(self.branches.read("Fork_Test","book_1",fork["branch_id"])["content"],
                         "The flame shifted.\nThen it rose.")


class BranchHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(self.tmp.name)/"config.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writer"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        self.story,self.root,self.original=seed(Store(cfg.data_dir()))
        self.server=serve(cfg)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        self.thread.join(timeout=3);self.tmp.cleanup()

    def post(self,route,data):
        req=urllib.request.Request(self.base+route,data=json.dumps(data).encode(),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)

    def get(self,route):
        with urllib.request.urlopen(self.base+route,timeout=10) as response:return json.load(response)

    def test_http_branch_workflow_and_view(self):
        source=Path(self.original).read_bytes()
        payload={"project_id":"Fork_Test","book_id":"book_1"}
        fork=self.post("/api/writer/story/branches/create",{
            **payload,"filename":Path(self.original).name,"name":"Alternative Plot"})
        self.assertTrue(fork["ok"])
        listing=self.get("/api/writer/story/branches?project_id=Fork_Test&book_id=book_1&chapter=Chapter%20One")
        self.assertEqual(len(listing["branches"]),1)
        loaded=self.post("/api/writer/story/branches/read",{
            **payload,"branch_id":fork["branch_id"]})
        changed=self.post("/api/writer/story/branches/append",{
            **payload,"branch_id":fork["branch_id"],
            "expected_revision":loaded["revision"],"content":"Alternate scene with a different outcome."})
        self.assertTrue(changed["canonical_unchanged"])
        diff=self.post("/api/writer/story/branches/compare",{
            **payload,"branch_id":fork["branch_id"]})
        self.assertTrue(diff["different"])
        self.assertEqual(Path(self.original).read_bytes(),source)
        for marker in ("Alternative Draft Branches","storyBranchCreate()","storyBranchSave()",
                       "storyBranchSelect","storyBranchCompare()"):
            self.assertIn(marker,render_page())

    def test_http_stale_or_invalid_branch_rejected(self):
        payload={"project_id":"Fork_Test","book_id":"book_1"}
        fork=self.post("/api/writer/story/branches/create",{
            **payload,"filename":Path(self.original).name,"name":"Alternate"})
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post("/api/writer/story/branches/append",{
                **payload,"branch_id":fork["branch_id"],
                "content":"Changed","expected_revision":"stale"})
        self.assertEqual(err.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/writer/story/branches/read",{
                **payload,"branch_id":"../secret"})


if __name__=="__main__":
    unittest.main(verbosity=2)
