"""Series outline, stable act IDs and verified corkboard draft links."""
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

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))

from app.storage import Store, jwrite
from app.storyforge import StoryForge
from app.series_outline import SeriesOutline
from app.scene_board import SceneBoard
from app.config import Config,DEFAULT_CONFIG
from app.server import serve
from app.ui import render_page


def seeded(store):
    root=store.folder("projects")/"KayockSaga"
    root.mkdir(parents=True,exist_ok=True)
    jwrite(root/"project.kayock-writer.json",{
        "project_id":"KayockSaga","title":"Kayock Saga",
        "books":[{"id":"book_1","title":"First Book"},
                 {"id":"book_2","title":"Second Book"}]
    })
    story=StoryForge(store)
    saved=story.draft_save_action({
        "project_id":"KayockSaga","book_id":"book_1",
        "chapter":"Chapter One","content":"A distant signal crossed the ocean.",
        "execute":True
    })
    assert saved["ok"],saved
    return story,root,saved["path"]


class SeriesPlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        self.story,self.root,self.draft=seeded(self.store)
        self.outline=SeriesOutline(self.store,self.story)
        self.board=SceneBoard(self.store,self.story)

    def tearDown(self):
        self.tmp.cleanup()

    def update(self,revision,action,**kwargs):
        return self.outline.change({
            "project_id":"KayockSaga","expected_revision":revision,
            "action":action,**kwargs
        })

    def make_act(self,book="book_1"):
        first=self.outline.read("KayockSaga")
        created=self.update(first["revision"],"act_add",
                            book_id=book,title="Arrival",summary="The signal")
        return created,created["outline"]["acts"][-1]["id"]

    def test_read_no_write_details_and_acts_stable_across_edits(self):
        path=self.root/"Planning"/"series_outline.json"
        view=self.outline.read("KayockSaga")
        self.assertTrue(view["read_only"])
        self.assertFalse(path.exists())
        details=self.update(view["revision"],"details",
                            series_title="The Fox Chronicles",
                            series_notes="A multi-book arc.")
        self.assertEqual(details["outline"]["series_title"],"The Fox Chronicles")
        created=self.update(details["revision"],"act_add",
                            book_id="book_1",title="Act One",summary="The beginning.")
        original_id=created["outline"]["acts"][0]["id"]
        changed=self.update(created["revision"],"act_edit",
                            act_id=original_id,title="Act One: Changed",
                            summary="A different act summary.")
        self.assertEqual(changed["outline"]["acts"][0]["id"],original_id)
        self.assertEqual(changed["outline"]["acts"][0]["title"],"Act One: Changed")
        with self.assertRaisesRegex(ValueError,"changed since"):
            self.update(details["revision"],"details",
                        series_title="Stale data",series_notes="")
        self.assertEqual(self.outline.read("KayockSaga")["outline"]["series_title"],
                         "The Fox Chronicles")
        self.assertTrue(list(self.store.folder("backups").glob(
            "series_outlines/series_outline_*.json")))
        self.assertEqual(
            (self.root/"project.kayock-writer.json").read_text(encoding="utf-8")
                .count("First Book"),1)

    def test_reject_unknown_book_bad_acts_and_damaged_outlines(self):
        before=self.outline.read("KayockSaga")
        with self.assertRaisesRegex(ValueError,"existing book"):
            self.update(before["revision"],"act_add",
                        book_id="fake",title="bad")
        with self.assertRaises(ValueError):
            self.update(before["revision"],"act_edit",act_id="unknown",
                        title="bad",summary="")
        self.update(before["revision"],"details",
                    series_title="Good",series_notes="Saved.")
        path=self.root/"Planning"/"series_outline.json"
        path.write_text("{corruption",encoding="utf-8")
        raw=path.read_bytes()
        with self.assertRaisesRegex(ValueError,"damaged"):
            self.outline.read("KayockSaga")
        with self.assertRaisesRegex(ValueError,"damaged"):
            self.update(before["revision"],"details",
                        series_title="Overwrite?",series_notes="")
        self.assertEqual(path.read_bytes(),raw)

    def test_scene_links_require_actual_book_act_and_verified_draft(self):
        created,act_id=self.make_act()
        rev=self.board.read("KayockSaga","book_1")["revision"]
        path=self.root/"Drafts"/"book_1"/Path(self.draft).name
        before_draft=path.read_bytes()
        board=self.board.change({
            "project_id":"KayockSaga","book_id":"book_1",
            "expected_revision":rev,"action":"add",
            "fields":{
                "title":"The Signal","chapter":"Chapter One",
                "act_id":act_id,"draft_filename":Path(self.draft).name,
                "summary":"A beacon appears."
            }
        })
        self.assertTrue(board["ok"])
        read=self.board.read("KayockSaga","book_1")
        self.assertEqual(read["board"]["cards"][0]["act_title"],"Arrival")
        self.assertTrue(read["board"]["cards"][0]["draft_valid"])
        self.assertEqual(read["board"]["cards"][0]["draft_filename"],Path(self.draft).name)
        self.assertEqual(path.read_bytes(),before_draft)
        with self.assertRaisesRegex(ValueError,"different chapter"):
            self.board.change({
                "project_id":"KayockSaga","book_id":"book_1",
                "expected_revision":read["revision"],"action":"update",
                "card_id":read["board"]["cards"][0]["id"],
                "fields":{"chapter":"Another Chapter"}
            })
        unchanged=self.board.read("KayockSaga","book_1")
        self.assertEqual(unchanged["revision"],read["revision"])
        with self.assertRaises(ValueError):
            self.board.change({
                "project_id":"KayockSaga","book_id":"book_1",
                "expected_revision":unchanged["revision"],"action":"add",
                "fields":{"title":"False link","draft_filename":"imaginary.md"}
            })
        with self.assertRaises(ValueError):
            self.board.change({
                "project_id":"KayockSaga","book_id":"book_2",
                "expected_revision":self.board.read("KayockSaga","book_2")["revision"],
                "action":"add","fields":{"title":"Foreign act","act_id":act_id}
            })

    def test_legacy_card_without_act_fields_still_loads(self):
        rev=self.board.read("KayockSaga","book_1")["revision"]
        made=self.board.change({
            "project_id":"KayockSaga","book_id":"book_1",
            "expected_revision":rev,"action":"add",
            "fields":{"title":"Legacy scene"}
        })
        file=self.root/"Scenes"/"Boards"/"book_1.json"
        old=json.loads(file.read_text(encoding="utf-8"))
        old["cards"][0].pop("act_id",None)
        old["cards"][0].pop("draft_filename",None)
        file.write_text(json.dumps(old),encoding="utf-8")
        view=self.board.read("KayockSaga","book_1")
        self.assertEqual(view["board"]["cards"][0]["act_id"],"")
        self.assertEqual(view["board"]["cards"][0]["draft_filename"],"")


class SeriesHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                   path=Path(self.tmp.name)/"config.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writer"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        self.story,self.root,self.draft=seeded(Store(cfg.data_dir()))
        self.server=serve(cfg)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        self.thread.join(timeout=3);self.tmp.cleanup()

    def get(self,path):
        with urllib.request.urlopen(self.base+path,timeout=10) as response:
            return json.load(response)

    def post(self,path,payload):
        req=urllib.request.Request(
            self.base+path,data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=10) as response:
            return json.load(response)

    def test_series_http_and_corkboard_ui(self):
        before=(self.root/"project.kayock-writer.json").read_bytes()
        outline=self.get("/api/writer/story/series_outline?project_id=KayockSaga")
        added=self.post("/api/writer/story/series_outline/change",{
            "project_id":"KayockSaga","expected_revision":outline["revision"],
            "action":"act_add","book_id":"book_1",
            "title":"Before the Storm","summary":"The prophecy arrives."})
        self.assertTrue(added["ok"])
        self.assertEqual(
            added["outline"]["acts"][0]["title"],"Before the Storm")
        self.assertEqual(before,(self.root/"project.kayock-writer.json").read_bytes())
        page=render_page()
        for marker in ("seriesPlanTitle","seriesActTitle",
                       "sceneBoardDraft","sceneBoardAct",
                       "seriesOutlineChange(","sceneBoardRefreshOptions()"):
            self.assertIn(marker,page)


if __name__=="__main__":
    unittest.main(verbosity=2)
