"""Offline Story Forge scene corkboard safety and HTTP regression tests."""
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.storage import Store, jwrite
from app.storyforge import StoryForge
from app.scene_board import SceneBoard, LANES
from app.config import Config, DEFAULT_CONFIG
from app.server import serve
from app.ui import render_page


class BoardTestBase:
    def seed_project(self, store):
        root = store.folder("projects") / "An_Adventure"
        root.mkdir(parents=True, exist_ok=True)
        manifest = root / "project.kayock-writer.json"
        jwrite(manifest, {
            "project_id": "An_Adventure", "title": "An Adventure",
            "books": [{"id": "book_1", "title": "First Book"},
                      {"id": "book_2", "title": "Second Book"}],
        })
        return root, manifest

    @staticmethod
    def add(board, rev, title, status="ideas", **fields):
        return board.change({
            "project_id": "An_Adventure", "book_id": "book_1",
            "expected_revision": rev, "action": "add", "status": status,
            "fields": {"title": title, **fields},
        })


class SceneBoardUnitTests(unittest.TestCase, BoardTestBase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))
        self.root, self.manifest = self.seed_project(self.store)
        self.forge = StoryForge(self.store)
        self.board = SceneBoard(self.store, self.forge)

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, book="book_1"):
        return self.board.read("An_Adventure", book)

    def test_read_is_no_write_and_separated_by_book(self):
        view = self.read()
        self.assertTrue(view["read_only"])
        self.assertEqual(view["board"]["cards"], [])
        self.assertEqual(view["lanes"], list(LANES))
        self.assertFalse((self.root / "Scenes" / "Boards" / "book_1.json").exists())
        self.assertNotEqual(view["revision"], self.read("book_2")["revision"])
        added = self.add(self.board, view["revision"], "First scene")
        self.assertTrue(added["ok"])
        self.assertEqual(len(self.read()["board"]["cards"]), 1)
        self.assertEqual(self.read("book_2")["board"]["cards"], [])

    def test_card_movement_update_parking_and_backup(self):
        manuscript = self.root / "Drafts" / "book_1" / "chapter_one_draft_v001.md"
        manuscript.parent.mkdir(parents=True, exist_ok=True)
        manuscript.write_text("Permanent original writing\n", encoding="utf-8")
        before_manifest = self.manifest.read_bytes()
        before_manuscript = manuscript.read_bytes()
        rev = self.read()["revision"]
        a = self.add(self.board, rev, "A", chapter="Chapter 1", summary="A start")
        b = self.add(self.board, a["revision"], "B")
        c = self.add(self.board, b["revision"], "C")
        ids = [x["id"] for x in c["board"]["cards"]]
        # Reorder C before A.
        moved = self.board.change({
            "project_id": "An_Adventure", "book_id": "book_1",
            "expected_revision": c["revision"], "action": "move",
            "card_id": ids[2], "status": "ideas", "before_id": ids[0],
        })
        self.assertEqual([x["title"] for x in moved["board"]["cards"]],
                         ["C", "A", "B"])
        revision = moved["revision"]
        edited = self.board.change({
            "project_id": "An_Adventure", "book_id": "book_1",
            "expected_revision": revision, "action": "update",
            "card_id": ids[0], "fields": {"beats": "Reversal"},
        })
        self.assertEqual(next(x for x in edited["board"]["cards"]
                              if x["id"] == ids[0])["beats"], "Reversal")
        parked = self.board.change({
            "project_id": "An_Adventure", "book_id": "book_1",
            "expected_revision": edited["revision"], "action": "park",
            "card_id": ids[1],
        })
        self.assertEqual(len(parked["board"]["cards"]), 3)
        self.assertEqual(next(x for x in parked["board"]["cards"]
                              if x["id"] == ids[1])["status"], "parked")
        self.assertEqual(manuscript.read_bytes(), before_manuscript)
        self.assertEqual(self.manifest.read_bytes(), before_manifest)
        backups = list(self.store.folder("backups").glob("scene_boards/book_1_*.json"))
        self.assertGreaterEqual(len(backups), 4)

    def test_stale_revision_and_invalid_moves_leave_bytes_unchanged(self):
        first = self.add(self.board, self.read()["revision"], "First")
        second = self.add(self.board, first["revision"], "Second")
        path = self.root / "Scenes" / "Boards" / "book_1.json"
        prior = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "changed since"):
            self.add(self.board, first["revision"], "Stale")
        with self.assertRaisesRegex(ValueError, "Target scene"):
            self.board.change({
                "project_id": "An_Adventure", "book_id": "book_1",
                "expected_revision": second["revision"], "action": "move",
                "card_id": first["card_id"], "status": "ideas",
                "before_id": "not-on-this-board",
            })
        self.assertEqual(path.read_bytes(), prior)

    def test_missing_project_wrong_book_and_damaged_board_rejected(self):
        with self.assertRaises(ValueError):
            self.board.read("Not_A_Project", "book_1")
        with self.assertRaises(ValueError):
            self.board.read("An_Adventure", "made_up_book")
        with self.assertRaises(ValueError):
            self.add(self.board, self.read()["revision"], "", summary="empty title")
        with self.assertRaises(ValueError):
            self.add(self.board, self.read()["revision"], "X",
                     chapter="x" * 200)
        created = self.add(self.board, self.read()["revision"], "Safe")
        path = self.root / "Scenes" / "Boards" / "book_1.json"
        path.write_text("{broken JSON", encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "damaged"):
            self.board.read("An_Adventure", "book_1")
        with self.assertRaisesRegex(ValueError, "damaged"):
            self.add(self.board, created["revision"], "Would overwrite")
        self.assertEqual(path.read_bytes(), before)

    def test_two_concurrent_editors_only_one_can_commit(self):
        view = self.read()
        outcomes = []
        barrier = threading.Barrier(2)

        def writer(name):
            barrier.wait(timeout=4)
            try:
                self.add(self.board, view["revision"], name)
                outcomes.append("ok")
            except ValueError as exc:
                self.assertIn("changed since", str(exc))
                outcomes.append("conflict")

        a = threading.Thread(target=writer, args=("Alpha",))
        b = threading.Thread(target=writer, args=("Beta",))
        a.start(); b.start()
        a.join(timeout=8); b.join(timeout=8)
        self.assertEqual(sorted(outcomes), ["conflict", "ok"])
        self.assertEqual(len(self.read()["board"]["cards"]), 1)


class SceneBoardHTTPTests(unittest.TestCase, BoardTestBase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                     path=Path(self.tmp.name) / "config.json")
        cfg.set("paths.data_dir", str(Path(self.tmp.name) / "data"))
        cfg.set("server.host", "127.0.0.1")
        cfg.set("server.port", 0)
        self.root, _ = self.seed_project(Store(cfg.data_dir()))
        self.server = serve(cfg)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()
        self.thread.join(timeout=3); self.tmp.cleanup()

    def get(self, params):
        path = "/api/writer/story/scene_board?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(self.url + path, timeout=8) as response:
            return json.load(response)

    def post(self, payload):
        req = urllib.request.Request(
            self.url + "/api/writer/story/scene_board/change",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.load(response)

    def test_end_to_end_and_ui_controls(self):
        view = self.get({"project_id": "An_Adventure", "book_id": "book_1"})
        result = self.post({
            "project_id": "An_Adventure", "book_id": "book_1",
            "expected_revision": view["revision"], "action": "add",
            "fields": {"title": "The Beacon", "beats": "A signal appears."},
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["board"]["cards"][0]["title"], "The Beacon")
        self.assertTrue(result["manuscript_unchanged"])
        for marker in ("sceneboard", "Visual Scene Corkboard", "sceneBoardMove(",
                       "sceneBoardSave()", "sceneBoardLanes", "sceneBoardRefresh()"):
            self.assertIn(marker, render_page())

    def test_http_rejects_stale_and_unlisted_book(self):
        old = self.get({"project_id": "An_Adventure", "book_id": "book_1"})
        self.post({"project_id": "An_Adventure", "book_id": "book_1",
                   "expected_revision": old["revision"], "action": "add",
                   "fields": {"title": "First"}})
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post({"project_id": "An_Adventure", "book_id": "book_1",
                       "expected_revision": old["revision"], "action": "add",
                       "fields": {"title": "Should reject"}})
        self.assertEqual(e.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError):
            self.get({"project_id": "An_Adventure", "book_id": "fake"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
