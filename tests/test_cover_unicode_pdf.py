"""Non-persistent JPEG covers and opt-in TrueType/Unicode PDF publishing."""
from __future__ import annotations

import base64
import io
import json
import sys
import shutil
import subprocess
import unicodedata
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.cover_art import decode_cover
from app.unicode_pdf import decode_font, make_unicode_pdf, TrueTypeFont
from app.pdf_publishing import make_pdf
from app.book_publishing import build_book_export
from app.book_assembly import BookAssembler
from app.publishing import build_export
from app.storage import Store,jwrite
from app.storyforge import StoryForge

# Tiny, valid, author-owned fixture image. No image library needed at runtime.
JPEG_B64=(
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL'
    'DBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/'
    '2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy'
    'MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAUAA8DASIAAhEBAxEB/8QA'
    'HwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUF'
    'BAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkK'
    'FhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1'
    'dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG'
    'x8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEB'
    'AQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAEC'
    'AxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRom'
    'JygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOE'
    'hYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU'
    '1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDgKKKK+6PQ'
    'CiiigD//2Q=='
)

def sample_book(cover=None,font=None):
    return {"title":"Cover & Typography","author":"Author Example",
            "chapters":[
                {"title":"Chapter One","text":"An old bell rang.\n\nA second paragraph."},
                {"title":"Chapter Two","text":"A closing chapter."},
            ],
            "cover":cover,"pdf_font":font}

def system_ttf():
    for filename in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ):
        file=Path(filename)
        if file.is_file() and file.stat().st_size <= 3*1024*1024:
            try:
                TrueTypeFont(file.read_bytes())
                return file.read_bytes()
            except ValueError:
                continue
    return None


class CoverUnitTests(unittest.TestCase):
    def test_jpeg_validates_and_private_exif_stripped(self):
        cover=decode_cover(JPEG_B64)
        self.assertEqual((cover["width"],cover["height"]),(15,20))
        self.assertGreater(cover["size"],200)
        original=base64.b64decode(JPEG_B64)
        exif=b"Exif\x00\x00GPS sample private EXIF"
        jpeg=original[:2]+b"\xff\xe1"+(len(exif)+2).to_bytes(2,"big")+exif+original[2:]
        out=decode_cover(base64.b64encode(jpeg).decode("ascii"))
        self.assertEqual(out["jpeg"],cover["jpeg"])
        self.assertNotIn(b"GPS sample",out["jpeg"])
        self.assertEqual(out["sha256"],cover["sha256"])

    def test_invalid_cover_rejected_without_processing_as_image(self):
        for data in ("garbled","",base64.b64encode(b"not a JPEG"*16).decode(),
                     base64.b64encode(b"\xff\xd8fake\xff\xd9").decode()):
            if data=="":
                self.assertIsNone(decode_cover(data))
            else:
                with self.assertRaises(ValueError):
                    decode_cover(data)

    def test_all_book_formats_embed_only_opted_cover(self):
        cover=decode_cover(JPEG_B64)
        for fmt in ("docx","epub","pdf"):
            result=build_book_export(sample_book(cover=cover),fmt)
            self.assertFalse(result["saved"])
            if fmt=="docx":
                with zipfile.ZipFile(io.BytesIO(result["body"])) as z:
                    self.assertEqual(z.read("word/media/cover.jpg"),cover["jpeg"])
                    self.assertIn("rId2",z.read("word/document.xml").decode("utf-8"))
                    self.assertIn("media/cover.jpg",z.read("word/_rels/document.xml.rels").decode("utf-8"))
                    ET.fromstring(z.read("word/document.xml"))
            elif fmt=="epub":
                with zipfile.ZipFile(io.BytesIO(result["body"])) as z:
                    self.assertEqual(z.read("OEBPS/cover.jpg"),cover["jpeg"])
                    self.assertIn('properties="cover-image"',z.read("OEBPS/package.opf").decode("utf-8"))
                    self.assertIn('src="cover.jpg"',z.read("OEBPS/title.xhtml").decode("utf-8"))
                    ET.fromstring(z.read("OEBPS/title.xhtml"))
            else:
                self.assertIn(b"/Subtype /Image",result["body"])
                self.assertIn(b"/DCTDecode",result["body"])
                self.assertIn(cover["jpeg"],result["body"])

    def test_default_formats_do_not_include_cover_image(self):
        for fmt in ("docx","epub","pdf"):
            result=build_book_export(sample_book(),fmt)
            if fmt=="docx":
                with zipfile.ZipFile(io.BytesIO(result["body"])) as z:
                    self.assertNotIn("word/media/cover.jpg",z.namelist())
            elif fmt=="epub":
                with zipfile.ZipFile(io.BytesIO(result["body"])) as z:
                    self.assertNotIn("OEBPS/cover.jpg",z.namelist())
            else:
                self.assertNotIn(b"/Subtype /Image",result["body"])

    def test_default_pdf_breaks_long_chapters_and_has_readable_page_count(self):
        long = sample_book()
        long["chapters"]=[{"title":"Extended",
                           "text":"A long paragraph of author words. " * 1500}]
        content=build_book_export(long,"pdf")["body"]
        self.assertGreater(content.count(b"/Type /Page /Parent"),2)
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertIn(b"startxref",content)


class UnicodeFontTests(unittest.TestCase):
    def test_default_rejects_unrepresentable_characters(self):
        with self.assertRaisesRegex(ValueError,"full Unicode"):
            make_pdf("Stars \u03A9","",[{"title":"Chapter","text":"A signal."}])

    def test_ttf_is_optional_and_invalid_upload_is_rejected(self):
        self.assertIsNone(decode_font(None))
        for value in ("definitely not base64",base64.b64encode(b"x"*1024).decode("ascii")):
            with self.assertRaises(ValueError):
                decode_font(value)

    def test_author_font_embeds_searchable_unicode_when_available(self):
        raw=system_ttf()
        if raw is None:
            self.skipTest("No system TrueType font is installed on this runner.")
        encoded=base64.b64encode(raw).decode("ascii")
        font=decode_font(encoded)
        self.assertGreater(font["size"],500)
        face = TrueTypeFont(font["raw"])
        self.assertNotEqual(face.glyph(ord("A")),0)
        self.assertNotEqual(face.glyph(ord("\u03A9")),0)
        manuscript={"title":"Alpha \u03A9","author":"A. Author",
                    "chapters":[{"title":"Night \u03A9","text":"An \u03A9 symbol and caf\u00E9."}]}
        pdf=make_unicode_pdf(manuscript["title"],manuscript["author"],
                             manuscript["chapters"],font)
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Subtype /Type0",pdf)
        self.assertIn(b"/FontFile2",pdf)
        self.assertIn(b"/ToUnicode",pdf)
        self.assertIn(b"03A9",pdf)  # ToUnicode mapping for Omega
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        # Poppler, when already present on an Actions runner, independently
        # verifies the ToUnicode extraction, not merely the raw PDF structure.
        if shutil.which("pdftotext"):
            with tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/"unicode_book.pdf"
                output.write_bytes(pdf)
                extracted=subprocess.run(
                    ["pdftotext", "-enc", "UTF-8", str(output), "-"],
                    capture_output=True, text=True, encoding="utf-8", timeout=20
                )
                self.assertEqual(extracted.returncode,0,extracted.stderr)
                # Explicit UTF-8 decoding is required on Windows: pdftotext
                # writes UTF-8, while the platform default may be cp1252.
                # NFKC also tolerates canonical Unicode presentation variants
                # without accepting replacement characters or missing text.
                normalized=unicodedata.normalize("NFKC",extracted.stdout)
                self.assertIn("Alpha Ω",normalized,
                              [hex(ord(x)) for x in extracted.stdout[:30]])
                self.assertIn("café",normalized)
                self.assertNotIn("\ufffd",normalized)
        book=sample_book(font=font,cover=decode_cover(JPEG_B64))
        result=build_book_export(book,"pdf")
        self.assertTrue(result["body"].startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Type0",result["body"])
        self.assertIn(b"/Subtype /Image",result["body"])
        self.assertIn(b"/DCTDecode",result["body"])
        passage=build_export({"format":"pdf","title":"Signal \u03A9",
            "author":"A. Author","text":"We saw \u03A9 above the sea.",
            "writing_type":"prose","pdf_ttf_base64":encoded})
        self.assertIn(b"/Subtype /Type0",passage["body"])

    def test_missing_glyph_is_explicit_if_font_available(self):
        raw=system_ttf()
        if raw is None:
            self.skipTest("No system TrueType font is installed on this runner.")
        font=decode_font(base64.b64encode(raw).decode("ascii"))
        with self.assertRaisesRegex(ValueError,"lacks glyph"):
            make_unicode_pdf("An unrenderable \U0010FFFF","",
                             [{"title":"Chapter","text":"Plain text"}],font)


class CoverAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))
        root=self.store.folder("projects")/"CoverStory"
        root.mkdir(parents=True,exist_ok=True)
        jwrite(root/"project.kayock-writer.json",{
            "project_id":"CoverStory","title":"Cover Story",
            "books":[{"id":"book_1","title":"First"}]})
        forge=StoryForge(self.store)
        saved=forge.draft_save_action({
            "project_id":"CoverStory","book_id":"book_1",
            "chapter":"One","content":"A story begins.",
            "execute":True})
        self.assertTrue(saved["ok"])
        self.original=Path(saved["path"])
        self.assembler=BookAssembler(forge)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self,cover=JPEG_B64,font=""):
        return {"project_id":"CoverStory","book_id":"book_1",
                "title":"Cover Story","author":"Author",
                "chapters":[{"chapter":"One","filename":self.original.name}],
                "cover_jpeg_base64":cover,"pdf_ttf_base64":font}

    def test_cover_selection_binds_to_preview_without_writing(self):
        before=self.original.read_bytes()
        withcover=self.payload()
        p=self.assembler.preview(withcover)
        self.assertTrue(p["cover_present"])
        self.assertEqual(p["cover_dimensions"],[15,20])
        verified=self.assembler.verified_book({
            **withcover,"confirmation_token":p["confirmation_token"]
        })
        self.assertTrue(verified["cover"])
        self.assertEqual(self.original.read_bytes(),before)
        without=self.payload(cover="")
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.assembler.verified_book({
                **without,"confirmation_token":p["confirmation_token"]})
        self.assertFalse(self.assembler.preview(without)["cover_present"])

    def test_selected_font_invalidates_preview(self):
        raw=system_ttf()
        if raw is None:
            self.skipTest("No system TrueType font on this runner.")
        font=base64.b64encode(raw).decode("ascii")
        original=self.payload()
        preview=self.assembler.preview(original)
        modified=self.payload(font=font)
        with self.assertRaisesRegex(ValueError,"changed since preview"):
            self.assembler.verified_book({
                **modified,"confirmation_token":preview["confirmation_token"]
            })
        result=self.assembler.preview(modified)
        self.assertTrue(result["unicode_pdf_font_present"])

if __name__=="__main__":
    unittest.main(verbosity=2)
