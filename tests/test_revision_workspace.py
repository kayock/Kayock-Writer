"""Explicit author revision preview, stale-source locking and append-only save."""
from __future__ import annotations

import hashlib
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
from app.revision_workspace import RevisionWorkspace
from app.storage import Store, jwrite
from app.storyforge import StoryForge
from app.draft_branches import DraftBranches
from app.server import serve
from app.ui import render_page

ORIGINAL="The lighthouse went dark.\n\nA bell rang from the pier."
CANDIDATE="The lighthouse stayed dark.\n\nA bell rang twice from the pier."


def seeded(store):
    root=store.folder("projects")/"RevisionTest"
    root.mkdir(parents=True,exist_ok=True)
    jwrite(root/"project.kayock-writer.json",{
        "project_id":"RevisionTest","title":"Revision Test",
        "books":[{"id":"book_1","title":"Book One"},{"id":"book_2","title":"Other Book"}]
    })
    forge=StoryForge(store)
    first=forge.draft_save_action({
        "project_id":"RevisionTest","book_id":"book_1",
        "chapter":"Chapter One","content":ORIGINAL,"execute":True
    })
    second=forge.draft_save_action({
        "project_id":"RevisionTest","book_id":"book_1",
        "chapter":"Another Chapter","content":"Another chapter remains unchanged.","execute":True
    })
    assert first["ok"] and second["ok"],(first,second)
    return root,forge,RevisionWorkspace(forge,DraftBranches(store,forge)),Path(first["path"])


class RevisionUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root,self.forge,self.workspace,self.saved=seeded(Store(Path(self.tmp.name)))
        self.manifest=self.root/"Drafts"/"book_1"/"draft_manifest.json"

    def tearDown(self):
        self.tmp.cleanup()

    def request(self,candidate=CANDIDATE):
        return {"project_id":"RevisionTest","book_id":"book_1",
                "chapter":"Chapter One","candidate":candidate}

    def test_load_and_preview_are_read_only_and_exact(self):
        before_src=self.saved.read_bytes()
        before_history=self.manifest.read_bytes()
        before_projects=list(self.root.rglob("*"))
        opts=self.workspace.options("RevisionTest","book_1")
        self.assertEqual(len(opts["chapters"]),2)
        current=self.workspace.load(self.request())
        self.assertEqual(current["text"],ORIGINAL)
        self.assertEqual(current["version"],1)
        self.assertEqual(current["sha256"],hashlib.sha256(ORIGINAL.encode()).hexdigest())
        preview=self.workspace.preview(self.request())
        self.assertTrue(preview["read_only"])
        self.assertTrue(preview["source_unchanged"])
        self.assertFalse(preview["candidate_saved"])
        self.assertEqual(preview["current_version"],1)
        self.assertEqual(preview["expected_next_version"],2)
        self.assertTrue(any("stayed dark" in line for line in preview["diff_lines"]))
        self.assertEqual(len(preview["confirmation_token"]),64)
        self.assertEqual(before_src,self.saved.read_bytes())
        self.assertEqual(before_history,self.manifest.read_bytes())
        self.assertEqual(before_projects,list(self.root.rglob("*")))

    def test_author_approval_only_appends_and_preserves_other_chapters(self):
        existing=self.saved.read_bytes()
        old_manifest=self.manifest.read_bytes()
        preview=self.workspace.preview(self.request())
        with self.assertRaisesRegex(ValueError,"Explicit"):
            self.workspace.accept({
                **self.request(),"confirmation_token":preview["confirmation_token"]
            })
        with self.assertRaisesRegex(ValueError,"Explicit"):
            self.workspace.accept({
                **self.request(),"confirmation_token":preview["confirmation_token"],
                "approved":"yes"
            })
        self.assertEqual(self.manifest.read_bytes(),old_manifest)
        approved=self.workspace.accept({
            **self.request(),"confirmation_token":preview["confirmation_token"],
            "approved":True
        })
        self.assertTrue(approved["accepted"])
        self.assertEqual(approved["canonical_version"],2)
        self.assertTrue(approved["original_versions_preserved"])
        self.assertEqual(self.saved.read_bytes(),existing)
        self.assertNotEqual(approved["canonical_path"],str(self.saved))
        self.assertEqual(self.forge._draft_body(
            Path(approved["canonical_path"]).read_text(encoding="utf-8")
        ),CANDIDATE)
        self.assertEqual(self.workspace.load(self.request())["text"],CANDIDATE)
        all_entries=json.loads(self.manifest.read_text(encoding="utf-8"))["versions"]
        one=[x for x in all_entries if x["chapter"]=="Chapter One"]
        another=[x for x in all_entries if x["chapter"]=="Another Chapter"]
        self.assertEqual(len(one),2)
        self.assertEqual(len(another),1)
        self.assertIn("author-approved manual revision",one[-1]["model"])
        with self.assertRaises(ValueError):
            self.workspace.accept({
                **self.request(),"confirmation_token":preview["confirmation_token"],
                "approved":True
            })

    def test_preview_rejected_after_canonical_history_changes(self):
        token=self.workspace.preview(self.request())["confirmation_token"]
        revised=self.forge.draft_save_action({
            "project_id":"RevisionTest","book_id":"book_1",
            "chapter":"Chapter One","content":"An independently revised draft.",
            "execute":True
        })
        self.assertTrue(revised["ok"])
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.workspace.accept({
                **self.request(),"approved":True,"confirmation_token":token
            })
        self.assertEqual(
            len([x for x in self.forge._load_draft_manifest(
                "RevisionTest","book_1")["versions"] if x["chapter"]=="Chapter One"]),2
        )

    def test_preview_rejected_after_candidate_or_unrelated_history_changes(self):
        token=self.workspace.preview(self.request())["confirmation_token"]
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.workspace.accept({
                **self.request(candidate=CANDIDATE+" A surprise ending."),
                "approved":True,"confirmation_token":token
            })
        self.forge.draft_save_action({
            "project_id":"RevisionTest","book_id":"book_1",
            "chapter":"Another Chapter","content":"Different notes in another chapter.",
            "execute":True
        })
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.workspace.accept({
                **self.request(),"approved":True,"confirmation_token":token
            })

    def test_source_file_corruption_and_manifest_damage_fail_closed(self):
        token=self.workspace.preview(self.request())["confirmation_token"]
        self.saved.write_text("not the recorded prose",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"differs from"):
            self.workspace.accept({
                **self.request(),"approved":True,"confirmation_token":token
            })
        self.manifest.write_text("{invalid",encoding="utf-8")
        damaged=self.manifest.read_bytes()
        with self.assertRaisesRegex(ValueError,"damaged"):
            self.workspace.preview(self.request())
        self.assertEqual(self.manifest.read_bytes(),damaged)

    def test_invalid_chapters_books_and_values_never_generate_truncated_versions(self):
        candidates=[
            "", "   ", "a"*80001, "Danger\n", "\nDanger",
            "# Header\nParagraph", "A\r\nB", "A\x00B"
        ]
        old_manifest=self.manifest.read_bytes()
        for candidate in candidates:
            with self.subTest(candidate=repr(candidate)[:40]):
                with self.assertRaises(ValueError):
                    self.workspace.preview(self.request(candidate))
        for payload in (
            {**self.request(),"book_id":"book_2"},
            {**self.request(),"book_id":"another"},
            {**self.request(),"project_id":"unrelated"},
            {**self.request(),"chapter":"Not Saved"},
        ):
            with self.assertRaises(ValueError):
                self.workspace.preview(payload)
        self.assertEqual(old_manifest,self.manifest.read_bytes())

    def test_display_limit_does_not_shorten_the_actual_candidate(self):
        many="\n".join("Line %03d rewritten with clear detail."%i for i in range(700))
        payload=self.request(many)
        preview=self.workspace.preview(payload)
        self.assertTrue(preview["diff_preview_truncated"])
        self.assertEqual(len(preview["diff_lines"]),400)
        saved=self.workspace.accept({
            **payload,"approved":True,
            "confirmation_token":preview["confirmation_token"]
        })
        text=self.forge._draft_body(Path(saved["canonical_path"]).read_text(encoding="utf-8"))
        self.assertEqual(text,many)
        self.assertIn("Line 699",text)

    def test_collision_file_never_overwritten(self):
        preview=self.workspace.preview(self.request())
        collision=self.root/"Drafts"/"book_1"/"chapter_chapter_one_draft_v002.md"
        collision.write_text("Different author's unrelated work.",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"already exists"):
            self.workspace.accept({
                **self.request(),"confirmation_token":preview["confirmation_token"],
                "approved":True
            })
        self.assertEqual(collision.read_text(encoding="utf-8"),
                         "Different author's unrelated work.")
        self.assertEqual(len(self.forge._load_draft_manifest(
            "RevisionTest","book_1")["versions"]),2)


class RevisionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                   path=Path(self.tmp.name)/"config.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writer"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        self.root,_,_,self.original=seeded(Store(cfg.data_dir()))
        self.server=serve(cfg)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:"+str(self.server.server_address[1])
        def forbidden_model(*a,**kw):
            raise AssertionError("Revision save must not call the model.")
        self.server.RequestHandlerClass.app.provider.chat=forbidden_model
        self.server.RequestHandlerClass.app.provider.stream_chat=forbidden_model

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        self.thread.join(timeout=4);self.tmp.cleanup()

    def req(self):
        return {"project_id":"RevisionTest","book_id":"book_1",
                "chapter":"Chapter One","candidate":CANDIDATE}

    def post(self,path,payload):
        request=urllib.request.Request(
            self.url+path,data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(request,timeout=12) as response:
            return json.load(response)

    def get(self,path):
        with urllib.request.urlopen(self.url+path,timeout=10) as response:
            return json.load(response)

    def test_options_load_preview_and_explicit_save_http(self):
        history=self.get("/api/writer/revision/options?project_id=RevisionTest&book_id=book_1")
        self.assertTrue(history["read_only"])
        self.assertEqual(len(history["chapters"]),2)
        loaded=self.post("/api/writer/revision/load",self.req())
        self.assertEqual(loaded["text"],ORIGINAL)
        preview=self.post("/api/writer/revision/preview",self.req())
        self.assertFalse(preview["candidate_saved"])
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.post("/api/writer/revision/accept",{
                **self.req(),"approved":True
            })
        self.assertEqual(missing.exception.code,400)
        before=self.original.read_bytes()
        result=self.post("/api/writer/revision/accept",{
            **self.req(),"confirmation_token":preview["confirmation_token"],
            "approved":True
        })
        self.assertEqual(result["canonical_version"],2)
        self.assertEqual(result["canonical_word_count"],len(CANDIDATE.split()))
        self.assertEqual(self.original.read_bytes(),before)
        self.assertEqual(self.post("/api/writer/revision/load",self.req())["text"],CANDIDATE)
        ui=render_page()
        for marker in (
            "Controlled Revision Workspace","revisionOriginal","revisionCandidate",
            "revisionApproval","revisionPreview()","revisionAccept()",
            "revisionApproveButton","revisionUseFinishingText()"
        ):
            self.assertIn(marker,ui)
        self.assertIn('id="revisionOriginal" class="big" readonly',ui)

    def test_reject_two_simultaneous_saves_from_one_confirmation(self):
        preview=self.post("/api/writer/revision/preview",self.req())
        payload={**self.req(),"confirmation_token":preview["confirmation_token"],
                 "approved":True}
        barrier=threading.Barrier(2)
        outcomes=[]
        def work():
            barrier.wait(timeout=6)
            try:
                self.post("/api/writer/revision/accept",payload)
                outcomes.append("saved")
            except urllib.error.HTTPError as exc:
                outcomes.append("rejected" if exc.code==400 else "error")
        threads=[threading.Thread(target=work,daemon=True) for i in range(2)]
        for t in threads:t.start()
        for t in threads:t.join(timeout=12)
        self.assertEqual(sorted(outcomes),["rejected","saved"])
        self.assertEqual(len([x for x in self.server.RequestHandlerClass.app.storyforge._load_draft_manifest(
            "RevisionTest","book_1")["versions"] if x["chapter"]=="Chapter One"]),2)

if __name__=="__main__":
    unittest.main(verbosity=2)
