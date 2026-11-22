"""Independently inspect the synthetic browser-downloaded EPUB and DOCX.

Extract a fixed allowlist of EPUB files for a separate Chromium rendering test.
This is browser XHTML verification, NOT certification by an EPUB reading app.
Only synthetic CI fixture files are ever inspected.
"""
from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

PROOFS = Path("test-results/release-proofs")
EPUB = PROOFS / "cover-edition.epub"
DOCX = PROOFS / "cover-edition.docx"
VIEWER = PROOFS / "epub-browser-view"
OPF_NS = "{http://www.idpf.org/2007/opf}"
XHTML_NS = "{http://www.w3.org/1999/xhtml}"
FILES = (
    "OEBPS/title.xhtml", "OEBPS/nav.xhtml",
    "OEBPS/chapter_001.xhtml", "OEBPS/chapter_002.xhtml",
    "OEBPS/style.css", "OEBPS/cover.jpg",
)

with zipfile.ZipFile(EPUB) as book:
    assert book.testzip() is None, "Corrupt EPUB entry"
    assert book.namelist()[0] == "mimetype", "EPUB mimetype must be first"
    assert book.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
    assert book.read("mimetype") == b"application/epub+zip"

    opf = ET.fromstring(book.read("OEBPS/package.opf"))
    spine = opf.find(OPF_NS + "spine")
    assert spine is not None
    assert [e.attrib["idref"] for e in spine] == ["cover", "c1", "c2"]
    manifest = opf.find(OPF_NS + "manifest")
    assert manifest is not None
    items = {item.attrib["id"]: item.attrib for item in manifest}
    assert items["coverimg"]["properties"] == "cover-image"
    assert items["coverimg"]["href"] == "cover.jpg"
    assert items["nav"]["properties"] == "nav"

    nav = ET.fromstring(book.read("OEBPS/nav.xhtml"))
    links = nav.findall(".//" + XHTML_NS + "a")
    assert [e.attrib["href"] for e in links] == [
        "chapter_001.xhtml#start", "chapter_002.xhtml#start"
    ]
    assert ["".join(e.itertext()) for e in links] == ["Chapter One", "Chapter Two"]

    title = ET.fromstring(book.read("OEBPS/title.xhtml"))
    assert "Fixture Manuscript Ω" in "".join(title.itertext())
    assert title.find(".//" + XHTML_NS + "img").attrib["src"] == "cover.jpg"
    a = ET.fromstring(book.read("OEBPS/chapter_001.xhtml"))
    b = ET.fromstring(book.read("OEBPS/chapter_002.xhtml"))
    assert "The lantern glowed above the empty shore." in "".join(a.itertext())
    assert "Beyond the harbor, the sea went still." in "".join(b.itertext())
    assert book.read("OEBPS/cover.jpg").startswith(b"\xff\xd8\xff")

    VIEWER.mkdir(parents=True, exist_ok=True)
    for entry in FILES:
        (VIEWER / Path(entry).name).write_bytes(book.read(entry))

with zipfile.ZipFile(DOCX) as word:
    assert word.testzip() is None, "Corrupt DOCX entry"
    assert word.read("word/media/cover.jpg").startswith(b"\xff\xd8\xff")
    assert b"media/cover.jpg" in word.read("word/_rels/document.xml.rels")
    document = ET.fromstring(word.read("word/document.xml"))
    assert "Chapter One" in "".join(document.itertext())

(VIEWER / "README.txt").write_text(
    "Synthetic EPUB XHTML extracted for Chromium rendering. "
    "Not a real EPUB e-reader compatibility test.\n", encoding="utf-8"
)
print("PASS: downloaded EPUB spine, TOC, cover, Unicode and chapters; DOCX cover.")
