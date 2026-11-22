"""Full-book preview, immutable sources, ZIP formats and local PDF regressions."""
from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))

from app.storage import Store,jwrite
from app.storyforge import StoryForge
from app.book_assembly import BookAssembler
from app.book_publishing import build_book_export
from app.publishing import build_export
from app.config import Config,DEFAULT_CONFIG
from app.server import serve
from app.ui import render_page

STORY = {
    "Chapter One": "The first chapter begins.\nThe bell rings.\n\nTime moves on.",
    "Chapter Two": "A second chapter arrives.\nA door opens.",
    "Chapter Three": "The end of a small book.\nA soft coda.",
}


def seed(store):
    root=store.folder("projects")/"Publication_Project"
    root.mkdir(parents=True,exist_ok=True)
    manifest=root/"project.kayock-writer.json"
    jwrite(manifest,{
        "project_id":"Publication_Project",
        "title":"Publication Project",
        "books":[{"id":"book_1","title":"An Actual Book"},
                 {"id":"book_2","title":"Other Book"}],
    })
    forge=StoryForge(store)
    files={}
    for chapter,text in STORY.items():
        result=forge.draft_save_action({
            "project_id":"Publication_Project","book_id":"book_1",
            "chapter":chapter,"content":text,"execute":True
        })
        assert result["ok"],result
        files[chapter]=Path(result["path"])
    # An alternate saved version of Chapter One is not silently substituted
    # for the one an author explicitly chooses.
    updated=forge.draft_save_action({
        "project_id":"Publication_Project","book_id":"book_1",
        "chapter":"Chapter One",
        "content":"The first chapter is completely rewritten.",
        "execute":True
    })
    assert updated["ok"],updated
    return forge,root,files,Path(updated["path"])


class BookAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        self.forge,self.root,self.original,self.updated=seed(self.store)
        self.assembler=BookAssembler(self.forge)

    def tearDown(self):
        self.tmp.cleanup()

    def selections(self):
        options=self.assembler.options("Publication_Project","book_1")
        groups={x["chapter"]:x for x in options["chapters"]}
        return [
            {"chapter":"Chapter Three",
             "filename":groups["Chapter Three"]["latest_filename"]},
            {"chapter":"Chapter One",
             "filename":groups["Chapter One"]["versions"][0]["filename"]},
            {"chapter":"Chapter Two",
             "filename":groups["Chapter Two"]["latest_filename"]},
        ]

    def payload(self,selected=None):
        return {
            "project_id":"Publication_Project","book_id":"book_1",
            "title":"The Northern Shore", "author":"The Writer",
            "chapters":selected or self.selections(),
        }

    def test_options_selected_versions_and_reorder_without_any_writes(self):
        before={p:p.read_bytes() for p in self.original.values()}
        before_manifest=(self.root/"project.kayock-writer.json").read_bytes()
        draft_manifest=(self.root/"Drafts"/"book_1"/"draft_manifest.json")
        draft_manifest_bytes=draft_manifest.read_bytes()
        options=self.assembler.options("Publication_Project","book_1")
        self.assertEqual(len(options["chapters"]),3)
        first=next(x for x in options["chapters"] if x["chapter"]=="Chapter One")
        self.assertEqual(len(first["versions"]),2)
        self.assertEqual(first["latest_filename"],self.updated.name)
        preview=self.assembler.preview(self.payload())
        self.assertTrue(preview["read_only"])
        self.assertEqual(preview["chapter_count"],3)
        self.assertEqual([x["title"] for x in preview["chapters"]],
                         ["Chapter Three","Chapter One","Chapter Two"])
        self.assertIn("The first chapter begins.",preview["chapters"][1]["excerpt"])
        self.assertEqual(sum(len(x.split()) for x in STORY.values()),preview["total_words"])
        self.assertEqual({p:p.read_bytes() for p in self.original.values()},before)
        self.assertEqual(before_manifest,(self.root/"project.kayock-writer.json").read_bytes())
        self.assertEqual(draft_manifest_bytes,draft_manifest.read_bytes())

    def test_selection_stale_on_source_or_order_and_refuses_bad_files(self):
        payload=self.payload()
        p=self.assembler.preview(payload)
        another=self.payload(list(reversed(payload["chapters"])))
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.assembler.verified_book({
                **another,"confirmation_token":p["confirmation_token"]
            })
        self.assertEqual(self.assembler.verified_book({
            **payload,"confirmation_token":p["confirmation_token"]
        })["chapters"][0]["title"],"Chapter Three")
        p2=self.assembler.preview(payload)
        self.original["Chapter Two"].write_text("Changed outside Writer",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"differs from"):
            self.assembler.verified_book({
                **payload,"confirmation_token":p2["confirmation_token"]
            })

    def test_new_canonical_version_invalidates_old_preview(self):
        payload=self.payload()
        p=self.assembler.preview(payload)
        changed=self.forge.draft_save_action({
            "project_id":"Publication_Project","book_id":"book_1",
            "chapter":"Chapter Two","content":"A new approved revision exists.",
            "execute":True
        })
        self.assertTrue(changed["ok"])
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.assembler.verified_book({
                **payload,"confirmation_token":p["confirmation_token"]
            })

    def test_reject_wrong_book_missing_version_duplicated_selection(self):
        original=self.payload()
        for changed in (
            {**original,"book_id":"book_2"},
            {**original,"book_id":"book_unknown"},
            {**original,"chapters":[original["chapters"][0]]*2},
            {**original,"chapters":[{"chapter":"Chapter Four","filename":"fake.md"}]},
            {**original,"chapters":[{"chapter":"Chapter One","filename":"../secret.md"}]},
            {**original,"chapters":[]},
        ):
            with self.assertRaises(ValueError):
                self.assembler.preview(changed)

    def test_damaged_manifest_is_not_assumed_empty(self):
        path=self.root/"Drafts"/"book_1"/"draft_manifest.json"
        path.write_text("{garbled",encoding="utf-8")
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,"damaged"):
            self.assembler.options("Publication_Project","book_1")
        with self.assertRaises(ValueError):
            self.assembler.preview(self.payload([
                {"chapter":"Chapter One","filename":self.original["Chapter One"].name}
            ]))
        self.assertEqual(path.read_bytes(),before)


class BookPackageTests(BookAssemblyTests):
    def test_docx_book_chapter_order_and_page_breaks(self):
        data=build_book_export(self.assembler.verified_book({
            **self.payload(),
            "confirmation_token":self.assembler.preview(self.payload())["confirmation_token"]
        }),"docx")
        self.assertFalse(data["saved"])
        with zipfile.ZipFile(io.BytesIO(data["body"])) as z:
            self.assertIsNone(z.testzip())
            for file in z.namelist():
                if file.endswith(".xml") or file.endswith(".rels"):
                    ET.fromstring(z.read(file))
            xml=z.read("word/document.xml").decode("utf-8")
            self.assertLess(xml.index("Chapter Three"),xml.index("Chapter One"))
            self.assertLess(xml.rindex("Chapter One"),xml.index("Chapter Two"))
            self.assertIn("The first chapter begins.",xml)
            self.assertNotIn("completely rewritten.",xml)
            self.assertEqual(xml.count("<w:pageBreakBefore/>"),3)

    def test_epub_multi_chapter_spine_toc_and_selected_version(self):
        payload=self.payload()
        book=self.assembler.verified_book({
            **payload,"confirmation_token":self.assembler.preview(payload)["confirmation_token"]
        })
        data=build_book_export(book,"epub")
        with zipfile.ZipFile(io.BytesIO(data["body"])) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.namelist()[0],"mimetype")
            self.assertEqual(z.getinfo("mimetype").compress_type,zipfile.ZIP_STORED)
            self.assertEqual(z.read("mimetype"),b"application/epub+zip")
            for name in z.namelist():
                if name.endswith((".xml",".xhtml")) or name=="OEBPS/package.opf":
                    ET.fromstring(z.read(name))
            navigation=z.read("OEBPS/nav.xhtml").decode()
            self.assertLess(navigation.index("Chapter Three"),
                            navigation.index("Chapter One"))
            self.assertLess(navigation.index("Chapter One"),
                            navigation.index("Chapter Two"))
            self.assertIn("The first chapter begins.",
                          z.read("OEBPS/chapter_002.xhtml").decode())
            self.assertNotIn("completely rewritten.",
                             z.read("OEBPS/chapter_002.xhtml").decode())
            package=z.read("OEBPS/package.opf").decode()
            self.assertEqual(package.count("<itemref idref=\"c"),3)
            self.assertIn('version="3.0"',package)

    def test_direct_pdf_contains_pages_no_silent_character_loss(self):
        payload=self.payload()
        book=self.assembler.verified_book({
            **payload,"confirmation_token":self.assembler.preview(payload)["confirmation_token"]
        })
        result=build_book_export(book,"pdf")
        binary=result["body"]
        self.assertTrue(binary.startswith(b"%PDF-1.4"))
        self.assertTrue(binary.rstrip().endswith(b"%%EOF"))
        self.assertEqual(len(re.findall(rb"/Type /Page\b",binary)),4)
        self.assertIn("xref",binary.decode("latin-1"))
        # PDF strings use hex WinAnsi bytes; verify the selected source,
        # not the latest discarded version, is what was encoded.
        self.assertIn("The first chapter begins.".encode("cp1252").hex().upper().encode(),binary)
        self.assertNotIn("The first chapter is completely rewritten.".encode("cp1252").hex().upper().encode(),binary)

    def test_pdf_unicode_is_rejected_not_transliterated(self):
        payload=self.payload()
        book=self.assembler.verified_book({
            **payload,"confirmation_token":self.assembler.preview(payload)["confirmation_token"]
        })
        book["chapters"][0]["text"]+="\nA symbol: 🌌"
        with self.assertRaisesRegex(ValueError,"DOCX/EPUB"):
            build_book_export(book,"pdf")
        self.assertGreater(len(build_book_export(book,"epub")["body"]),500)
        self.assertGreater(len(build_book_export(book,"docx")["body"]),500)

    def test_single_passage_pdf_is_available(self):
        pdf=build_export({
            "format":"pdf","title":"A Short Poem",
            "author":"The Writer","writing_type":"poem",
            "text":"A single line.\nAnd one more."
        })
        self.assertEqual(pdf["content_type"],"application/pdf")
        self.assertTrue(pdf["body"].startswith(b"%PDF-1.4"))


class BookHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(self.tmp.name)/"cfg.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writer"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        self.forge,self.root,self.original,self.updated=seed(Store(cfg.data_dir()))
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
        request=urllib.request.Request(
            self.base+path,data=json.dumps(payload).encode(),
            headers={"Content-Type":"application/json"},method="POST")
        return urllib.request.urlopen(request,timeout=10)

    def selections(self):
        options=self.get("/api/writer/publishing/book/options?project_id=Publication_Project&book_id=book_1")
        return [{"chapter":g["chapter"],"filename":g["latest_filename"]}
                for g in options["chapters"]]

    def test_preview_and_download_all_formats_are_explicit_and_nondestructive(self):
        selections=self.selections()
        payload={"project_id":"Publication_Project","book_id":"book_1",
                 "title":"The Northern Shore","author":"An Author",
                 "chapters":selections}
        snapshots={p:p.read_bytes() for p in self.original.values()}
        with self.post("/api/writer/publishing/book/preview",payload) as response:
            preview=json.load(response)
        self.assertTrue(preview["read_only"])
        self.assertEqual(preview["chapter_count"],3)
        for fmt in ("docx","epub","pdf"):
            with self.post("/api/writer/publishing/book/export",{
                **payload,"format":fmt,"confirmation_token":preview["confirmation_token"]
            }) as r:
                self.assertEqual(r.status,200)
                self.assertIn("attachment",r.headers["Content-Disposition"])
                self.assertEqual(r.headers["Cache-Control"],"no-store")
                body=r.read()
                self.assertGreater(len(body),500)
                if fmt=="pdf":
                    self.assertTrue(body.startswith(b"%PDF-"))
                else:
                    with zipfile.ZipFile(io.BytesIO(body)) as z:
                        self.assertIsNone(z.testzip())
        self.assertEqual({p:p.read_bytes() for p in self.original.values()},snapshots)
        for marker in ("Full-Book Assembly","bookPublishPreview()","bookPublishDownload('docx')",
                       "bookPublishDownload('epub')","bookPublishDownload('pdf')"):
            self.assertIn(marker,render_page())

    def test_export_rejects_missing_or_stale_preview(self):
        selections=self.selections()
        payload={"project_id":"Publication_Project","book_id":"book_1",
                 "title":"A Book","author":"","chapters":selections}
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.post("/api/writer/publishing/book/export",{**payload,"format":"docx"})
        self.assertEqual(context.exception.code,400)
        with self.post("/api/writer/publishing/book/preview",payload) as response:
            token=json.load(response)["confirmation_token"]
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.post("/api/writer/publishing/book/export",{
                **payload,"title":"Altered title","format":"epub","confirmation_token":token
            })
        self.assertEqual(context.exception.code,400)


if __name__=="__main__":
    unittest.main(verbosity=2)
