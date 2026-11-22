"""Novel Forge regression tests for data-preserving saves and renames."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.storage import Store
from app.novelforge import NovelForge


class NovelSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        self.forge=NovelForge(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_second_save_keeps_previous_json_and_markdown_backups(self):
        first=self.forge.save_universe({
            "universe":"My Universe","premise":"Original premise",
            "characters":["Elena is alive."]
        })
        self.assertTrue(first["ok"])
        md=Path(first["markdown"])
        self.assertIn("Original premise",md.read_text(encoding="utf-8"))
        second=self.forge.save_universe({
            "universe":"My Universe","premise":"New premise",
            "characters":["Elena is alive."]
        })
        self.assertTrue(second["ok"])
        self.assertIn("New premise",md.read_text(encoding="utf-8"))
        json_backups=list((Path(self.tmp.name)/"Backups"/"KayockWriter"/"universes").glob("My_Universe_*.json"))
        md_backups=list((Path(self.tmp.name)/"Backups"/"KayockWriter"/"universe_markdown").glob("My_Universe_*.md"))
        self.assertEqual(len(json_backups),1)
        self.assertEqual(len(md_backups),1)
        self.assertEqual(json.loads(json_backups[0].read_text(encoding="utf-8"))["premise"],"Original premise")
        self.assertIn("Original premise",md_backups[0].read_text(encoding="utf-8"))

    def test_same_slug_rename_cannot_delete_active_universe(self):
        saved=self.forge.save_universe({
            "universe":"A Universe","premise":"Keep this work",
            "characters":["Elena"]
        })
        self.assertTrue(saved["ok"])
        renamed=self.forge.rename_universe({
            "name":"A_Universe", "new_title":"A_Universe"
        })
        self.assertTrue(renamed["ok"],renamed)
        item=Path(self.tmp.name)/"NovelForge"/"A_Universe.json"
        self.assertTrue(item.is_file())
        data=json.loads(item.read_text(encoding="utf-8"))
        self.assertEqual(data["premise"],"Keep this work")
        self.assertEqual(data["characters"],["Elena"])

    def test_duplicate_target_collision_does_not_overwrite_original_copy(self):
        self.forge.save_universe({"universe":"Original","premise":"Initial"})
        self.forge.save_universe({"universe":"Existing Copy","premise":"Do not overwrite"})
        duplicate=self.forge.duplicate_universe({
            "name":"Original","new_title":"Existing Copy"
        })
        self.assertFalse(duplicate["ok"])
        saved=self.forge.read_universe("Existing Copy")
        self.assertEqual(saved["premise"],"Do not overwrite")


if __name__=="__main__":
    unittest.main(verbosity=2)
