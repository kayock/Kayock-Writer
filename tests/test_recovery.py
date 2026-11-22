"""Recovery tests: exact snapshots, stale previews, corrupt backups, HTTP approval."""
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

from app.config import Config, DEFAULT_CONFIG
from app.novelforge import NovelForge
from app.recovery import UniverseRecovery
from app.server import serve
from app.storage import Store


class RecoveryUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        self.forge=NovelForge(self.store)
        self.recovery=UniverseRecovery(self.store,self.forge)
        saved=self.forge.save_universe({
            "universe":"My Universe","premise":"Original premise",
            "characters":["Elena"],"timeline":["Day 1: the ship arrives"]
        })
        self.assertTrue(saved["ok"],saved)
        self.json_path=Path(saved["path"])
        old=json.loads(self.json_path.read_text(encoding="utf-8"))
        old["custom_world_rule"]={"secret":"Retain this exact snapshot field"}
        self.json_path.write_text(json.dumps(old,ensure_ascii=False),encoding="utf-8")
        updated=self.forge.save_universe({
            "universe":"My Universe","premise":"New premise",
            "characters":["Marcus"],"timeline":["Day 9: Marcus returns"]
        })
        self.assertTrue(updated["ok"],updated)

    def tearDown(self):
        self.tmp.cleanup()

    def test_recovery_preview_is_read_only_then_restore_keeps_current_backup(self):
        snapshots=self.recovery.list_backups("My_Universe")
        self.assertEqual(len(snapshots["backups"]),1)
        backup_id=snapshots["backups"][0]["id"]
        current=self.json_path.read_bytes()
        mirror=self.forge.novel_md_path("My_Universe")
        existing_mirror=mirror.read_bytes()
        preview=self.recovery.preview("My_Universe",backup_id)
        self.assertEqual(preview["snapshot"]["premise"],"Original premise")
        self.assertEqual(preview["current"]["premise"],"New premise")
        self.assertEqual(self.json_path.read_bytes(),current)
        self.assertEqual(mirror.read_bytes(),existing_mirror)
        result=self.recovery.restore("My_Universe",backup_id,preview["confirmation_token"])
        self.assertTrue(result["restored"])
        restored=json.loads(self.json_path.read_text(encoding="utf-8"))
        self.assertEqual(restored["premise"],"Original premise")
        self.assertEqual(restored["characters"],["Elena"])
        self.assertEqual(restored["custom_world_rule"],{"secret":"Retain this exact snapshot field"})
        self.assertIn("Original premise",mirror.read_text(encoding="utf-8"))
        self.assertIn("Elena",mirror.read_text(encoding="utf-8"))
        self.assertTrue((self.store.folder("backups")/"universes"/result["saved_current_backup"]).is_file())
        prior=json.loads((self.store.folder("backups")/"universes"/result["saved_current_backup"]).read_text(encoding="utf-8"))
        self.assertEqual(prior["premise"],"New premise")
        self.assertIsNotNone(result["saved_current_markdown_backup"])

    def test_stale_preview_never_overwrites_newer_author_work(self):
        backup_id=self.recovery.list_backups("My_Universe")["backups"][0]["id"]
        preview=self.recovery.preview("My_Universe",backup_id)
        newer=self.forge.save_universe({"universe":"My Universe","premise":"Another edit"})
        self.assertTrue(newer["ok"])
        before=self.json_path.read_bytes()
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.recovery.restore("My_Universe",backup_id,preview["confirmation_token"])
        self.assertEqual(self.json_path.read_bytes(),before)

    def test_changed_backup_fails_confirmation_and_preview(self):
        backup_id=self.recovery.list_backups("My_Universe")["backups"][0]["id"]
        preview=self.recovery.preview("My_Universe",backup_id)
        file=self.store.folder("backups")/"universes"/backup_id
        snapshot=json.loads(file.read_text(encoding="utf-8"))
        snapshot["premise"]="Backup was edited"
        file.write_text(json.dumps(snapshot),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.recovery.restore("My_Universe",backup_id,preview["confirmation_token"])

    def test_unrelated_or_damaged_backup_is_never_accepted(self):
        with self.assertRaises(ValueError):
            self.recovery.preview("My_Universe","../outside.json")
        with self.assertRaises(ValueError):
            self.recovery.preview("My_Universe","Other_Universe_20260101_deadbeef.json")
        backup_id=self.recovery.list_backups("My_Universe")["backups"][0]["id"]
        file=self.store.folder("backups")/"universes"/backup_id
        file.write_text("{corrupted",encoding="utf-8")
        self.assertEqual(self.recovery.list_backups("My_Universe")["backups"],[])
        with self.assertRaises(ValueError):
            self.recovery.preview("My_Universe",backup_id)

    def test_missing_confirmation_never_writes(self):
        backup_id=self.recovery.list_backups("My_Universe")["backups"][0]["id"]
        before=self.json_path.read_bytes()
        with self.assertRaisesRegex(ValueError,"Preview"):
            self.recovery.restore("My_Universe",backup_id,"")
        self.assertEqual(self.json_path.read_bytes(),before)


class RecoveryHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(self.tmp.name)/"config.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writer"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        self.writer=serve(cfg)
        self.thread=threading.Thread(target=self.writer.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.writer.server_address[1])
        self.post("/api/novelforge/save",{"universe":"Atlas","premise":"Version one"})
        self.post("/api/novelforge/save",{"universe":"Atlas","premise":"Version two"})

    def tearDown(self):
        self.writer.shutdown()
        self.writer.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def post(self,path,data):
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode(),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req,timeout=10) as response:
            return json.load(response)

    def get(self,path):
        with urllib.request.urlopen(self.base+path,timeout=10) as response:
            return json.load(response)

    def test_restore_requires_preview_confirmation_and_stays_local(self):
        backups=self.get("/api/novelforge/backups?name=Atlas")
        self.assertTrue(backups["ok"])
        item=backups["backups"][0]["id"]
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/novelforge/backups/restore",{"universe":"Atlas","backup_id":item})
        preview=self.post("/api/novelforge/backups/preview",{"universe":"Atlas","backup_id":item})
        self.assertTrue(preview["read_only"])
        result=self.post("/api/novelforge/backups/restore",{
            "universe":"Atlas","backup_id":item,
            "confirmation_token":preview["confirmation_token"]
        })
        self.assertTrue(result["restored"],result)
        read=self.get("/api/novelforge/read?name=Atlas")
        self.assertEqual(read["premise"],"Version one")
        self.assertTrue(result["saved_current_backup"])


if __name__=="__main__":
    unittest.main(verbosity=2)
