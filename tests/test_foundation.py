"""Regression tests for v1.2 storage and the opt-in canon prototype."""
from __future__ import annotations
import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.canon import CanonStore
from app.storage import Store, atomic_write_text, jread, jwrite


class AtomicStorageTests(unittest.TestCase):
    def test_json_roundtrip_and_no_temp_files(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "work.json"
            jwrite(target, {"poem": "first stanza\nsecond stanza"})
            jwrite(target, {"poem": "changed", "revision": 2})
            self.assertEqual(jread(target)["revision"], 2)
            self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_failed_serialization_does_not_replace_original(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "work.json"
            jwrite(target, {"draft": "keep me"})
            with self.assertRaises(TypeError):
                jwrite(target, {"invalid": object()})
            self.assertEqual(jread(target), {"draft": "keep me"})

    def test_backups_are_unique_within_same_second(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            target = Path(directory) / "chapter.md"
            target.write_text("Original\n", encoding="utf-8")
            backup1 = store.backup_file(target)
            backup2 = store.backup_file(target)
            self.assertNotEqual(backup1, backup2)
            self.assertEqual(backup1.read_text(encoding="utf-8"), "Original\n")
            self.assertEqual(backup2.read_text(encoding="utf-8"), "Original\n")


class CanonTests(unittest.TestCase):
    def test_proposal_requires_evidence_and_never_modifies_universe(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            canon = CanonStore(store)
            novel = store.folder("novel_forge") / "My_Universe.json"
            novel.write_text('{"universe":"My Universe"}', encoding="utf-8")
            before = novel.read_bytes()
            with self.assertRaises(ValueError):
                canon.propose("My Universe", "character", "Elena", "Scar on left arm", [])
            new = canon.propose("My Universe", "character", "Elena",
                                "Scar on left arm", [{"source": "Chapter 3", "quote": "her left arm"}],
                                chapter="03", world_time="day 4")
            self.assertEqual(canon.approved_context("My Universe"), [])
            self.assertEqual(canon.list_facts("My Universe", "proposed")["facts"][0]["id"], new["fact"]["id"])
            canon.review("My Universe", new["fact"]["id"], "approved")
            self.assertEqual(len(canon.approved_context("My Universe")), 1)
            with self.assertRaises(ValueError):
                canon.review("My Universe", new["fact"]["id"], "rejected")
            self.assertEqual(novel.read_bytes(), before)

    def test_rejection_does_not_enter_context(self):
        with tempfile.TemporaryDirectory() as directory:
            canon = CanonStore(Store(Path(directory)))
            proposal = canon.propose("World", "event", "Arrival", "The ship arrived",
                                     [{"source": "Chapter 1", "quote": "ship entered harbor"}])
            canon.review("World", proposal["fact"]["id"], "rejected")
            self.assertEqual(canon.approved_context("World"), [])

    def test_corrupt_index_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            canon = CanonStore(Store(Path(directory)))
            canon.propose("World", "rule", "Magic", "No teleportation",
                          [{"source": "World guide", "quote": "Teleportation is impossible"}])
            path = Path(directory) / "NovelForge" / ".canon" / "World" / "facts.json"
            path.write_text("not valid JSON", encoding="utf-8")
            with self.assertRaises(ValueError):
                canon.propose("World", "event", "Arrival", "The ship arrived",
                              [{"source": "Ch1", "quote": "arrived"}])
            self.assertEqual(path.read_text(encoding="utf-8"), "not valid JSON")


if __name__ == "__main__":
    unittest.main()
