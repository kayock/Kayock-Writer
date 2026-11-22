"""In-memory DOCX / EPUB3 exports: structural validity, fidelity and HTTP safety."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.publishing import build_export
from app.config import Config,DEFAULT_CONFIG
from app.server import serve
from app.ui import render_page

ORIGINAL="The sea was still.\nUntil the bells began.\n\nThen the tide returned.\n"
POEM="First line,\nSecond line.\n\nA new stanza,\nA final line."


def request(fmt="docx",text=ORIGINAL,**kwargs):
    data={"format":fmt,"title":"The Shore & the City","author":"A. Writer",
          "writing_type":"prose","text":text}
    data.update(kwargs)
    return data


class PackageTests(unittest.TestCase):
    def test_docx_package_is_xml_valid_and_keeps_unicode_and_lines(self):
        original="In the México sky,\nThe bells answered.\n\nA \"strange\" & final stanza."
        result=build_export(request(text=original))
        self.assertTrue(result["ok"])
        self.assertFalse(result["saved"])
        self.assertTrue(result["source_unchanged"])
        self.assertEqual(result["filename"],"The_Shore_the_City.docx")
        self.assertIn("wordprocessingml",result["content_type"])
        with zipfile.ZipFile(io.BytesIO(result["body"])) as z:
            self.assertIsNone(z.testzip())
            self.assertIn("[Content_Types].xml",z.namelist())
            self.assertIn("word/document.xml",z.namelist())
            self.assertIn("word/styles.xml",z.namelist())
            self.assertIn("word/_rels/document.xml.rels",z.namelist())
            for name in z.namelist():
                if name.endswith((".xml",".rels")) or name=="[Content_Types].xml":
                    ET.fromstring(z.read(name))
            root=ET.fromstring(z.read("word/document.xml"))
            w="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            paragraphs=root.findall(".//"+w+"p")
            self.assertGreaterEqual(len(paragraphs),4)
            self.assertEqual("".join(el.text or "" for el in
                root.findall(".//"+w+"t")).count("México"),1)
            self.assertEqual(len(root.findall(".//"+w+"br")),1)
            self.assertTrue(any("A. Writer" in "".join(el.text or "" for el in p.findall(".//"+w+"t"))
                                for p in paragraphs))

    def test_epub3_zip_metadata_navigation_and_stanza_preservation(self):
        data=build_export(request("epub",POEM,writing_type="poem"))
        with zipfile.ZipFile(io.BytesIO(data["body"])) as z:
            self.assertEqual(z.namelist()[0],"mimetype")
            self.assertEqual(z.getinfo("mimetype").compress_type,zipfile.ZIP_STORED)
            self.assertEqual(z.read("mimetype"),b"application/epub+zip")
            self.assertIsNone(z.testzip())
            for name in ("META-INF/container.xml","OEBPS/package.opf",
                         "OEBPS/nav.xhtml","OEBPS/chapter.xhtml"):
                ET.fromstring(z.read(name))
            chapter=z.read("OEBPS/chapter.xhtml").decode("utf-8")
            self.assertIn("First line,",chapter)
            self.assertIn("Second line.",chapter)
            self.assertIn("A new stanza,",chapter)
            self.assertIn("<br />",chapter)
            self.assertEqual(chapter.count('class="stanza"'),2)
            package=z.read("OEBPS/package.opf").decode("utf-8")
            self.assertIn("version=\"3.0\"",package)
            self.assertIn("A. Writer",package)
            self.assertIn("dcterms:modified",package)
        self.assertEqual(data["filename"],"The_Shore_the_City.epub")

    def test_markup_is_escaped_never_executable(self):
        content="<script>alert('hi')</script> & <b>not HTML</b>"
        for fmt in ("docx","epub"):
            result=build_export(request(fmt,content))
            with zipfile.ZipFile(io.BytesIO(result["body"])) as z:
                body=z.read("word/document.xml" if fmt=="docx" else "OEBPS/chapter.xhtml").decode()
                self.assertNotIn("<script>",body)
                self.assertIn("&lt;script&gt;",body)
                ET.fromstring(body)

    def test_invalid_or_too_long_text_refused_without_truncation(self):
        for payload in (
            request(format="invalid"),
            request(text=""),
            request(text="a"*80001),
            request(text="hello\x00world"),
            request(title="../\nDangerous"),
        ):
            if payload.get("title")=="../\nDangerous":
                # The title is allowed as content, but filename must be safe.
                result=build_export(payload)
                self.assertNotIn("/",result["filename"])
                continue
            with self.assertRaises(ValueError):
                build_export(payload)

    def test_no_files_created_by_in_memory_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            before=list(Path(tmp).rglob("*"))
            for fmt in ("docx","epub"):
                self.assertGreater(len(build_export(request(fmt))["body"]),250)
            self.assertEqual(list(Path(tmp).rglob("*")),before)


class PublishingHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(self.tmp.name)/"cfg.json")
        cfg.set("paths.data_dir",str(Path(self.tmp.name)/"writing"))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        self.server=serve(cfg)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        self.thread.join(timeout=3);self.tmp.cleanup()

    def post(self,payload):
        req=urllib.request.Request(
            self.base+"/api/writer/publishing/export",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        return urllib.request.urlopen(req,timeout=8)

    def test_two_formats_download_without_writing_manuscripts(self):
        for fmt in ("docx","epub"):
            with self.post(request(fmt)) as r:
                self.assertEqual(r.status,200)
                self.assertIn('attachment;',r.headers.get("Content-Disposition",""))
                self.assertEqual(r.headers.get("Cache-Control"),"no-store")
                body=r.read()
                with zipfile.ZipFile(io.BytesIO(body)) as z:
                    self.assertIsNone(z.testzip())
        root=Path(self.tmp.name)/"writing"
        self.assertEqual(list(root.rglob("*.md")),[])
        self.assertEqual(list(root.rglob("*.docx")),[])
        self.assertEqual(list(root.rglob("*.epub")),[])
        html=render_page()
        for marker in ("finishingExportPackage('docx')",
                       "finishingExportPackage('epub')",
                       "finishPublishingStatus","finishAuthor"):
            self.assertIn(marker,html)

    def test_invalid_input_returns_400_not_partial_zip(self):
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post(request("epub","bad\x00XML"))
        self.assertEqual(err.exception.code,400)


if __name__=="__main__":
    unittest.main(verbosity=2)
