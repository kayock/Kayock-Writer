"""Book-level DOCX, EPUB 3 and PDF from an explicitly previewed chapter assembly.

The BookAssembler verifies all source chapters. This module consumes the
in-memory selection only; it neither reads nor writes manuscript files.
"""
from __future__ import annotations

import html
import io
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict

from .publishing import MIMES, _docx, _docx_paragraph, _safe_xml
from .pdf_publishing import make_pdf


def _filename(title: str, fmt: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", title)[:80].strip("_") or "Kayock_Book"
    return name + "." + fmt


def _cover_docx_paragraph(cover: Dict[str, Any]) -> str:
    """WordprocessingML inline drawing referencing image relationship rId2."""
    width, height = cover["width"], cover["height"]
    scale = min(5.6 * 914400 / width, 6.25 * 914400 / height)
    cx, cy = int(width * scale), int(height * scale)
    return (
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
        '<wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        '<wp:extent cx="' + str(cx) + '" cy="' + str(cy) + '"/>'
        '<wp:docPr id="1" name="Author supplied cover"/>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:nvPicPr><pic:cNvPr id="0" name="Cover.jpg"/><pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        '<a:ext cx="' + str(cx) + '" cy="' + str(cy) + '"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline>'
        '</w:drawing></w:r></w:p>'
    )


def _docx_book(book: Dict[str, Any]) -> bytes:
    # Retain the existing DOCX package structure, content-types and relationships.
    original = _docx({"title": book["title"], "author": book["author"], "text": ""})
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        entries = {name: z.read(name) for name in z.namelist()}
    original_document = entries["word/document.xml"].decode("utf-8")
    before, after = original_document.split("<w:body>", 1)
    _, tail = after.split("<w:sectPr>", 1)
    cover = book.get("cover")
    first = _cover_docx_paragraph(cover) if cover else ""
    first += _docx_paragraph(book["title"], "Title")
    if book["author"]:
        first += _docx_paragraph(book["author"], "Subtitle")
    # A static contents list is editable in Word; navigation is not yet
    # a dynamically generated page-number index.
    contents = _docx_paragraph("Contents", "Heading1")
    for number, chapter in enumerate(book["chapters"], 1):
        contents += _docx_paragraph(str(number) + ". " + chapter["title"])
    paragraphs = [first, contents]
    for chapter in book["chapters"]:
        heading = _docx_paragraph(chapter["title"], "Heading1")
        heading = heading.replace(
            '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>',
            '<w:pPr><w:pStyle w:val="Heading1"/><w:pageBreakBefore/></w:pPr>',
            1
        )
        paragraphs.append(heading)
        for paragraph in re.split(r"\n[ \t]*\n", chapter["text"]):
            paragraphs.append(_docx_paragraph(paragraph))
    entries["word/document.xml"] = (
        before + "<w:body>" + "".join(paragraphs) + "<w:sectPr>" + tail
    ).encode("utf-8")
    styles = entries["word/styles.xml"].decode("utf-8")
    chapter_style = (
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/><w:pPr><w:spacing w:before="220" w:after="220"/>'
        '<w:keepNext/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
    )
    entries["word/styles.xml"] = styles.replace(
        "</w:styles>", chapter_style + "</w:styles>"
    ).encode("utf-8")
    if cover:
        entries["word/media/cover.jpg"] = cover["jpeg"]
        content_types = entries["[Content_Types].xml"].decode("utf-8")
        entries["[Content_Types].xml"] = content_types.replace(
            '</Types>',
            '<Default Extension="jpg" ContentType="image/jpeg"/></Types>'
        ).encode("utf-8")
        rels = entries["word/_rels/document.xml.rels"].decode("utf-8")
        entries["word/_rels/document.xml.rels"] = rels.replace(
            '</Relationships>',
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="media/cover.jpg"/></Relationships>'
        ).encode("utf-8")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return out.getvalue()


def _epub_book(book: Dict[str, Any]) -> bytes:
    title, author = (html.escape(book[k], quote=True)
                     for k in ("title", "author"))
    uid = "urn:uuid:" + str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    chapter_files = []
    nav_items = []
    opf_items = []
    spine_items = []
    for idx, chapter in enumerate(book["chapters"], 1):
        name = "chapter_%03d.xhtml" % idx
        heading = html.escape(chapter["title"], quote=True)
        parts = []
        for paragraph in re.split(r"\n[ \t]*\n", chapter["text"]):
            lines = [html.escape(line, quote=True) for line in paragraph.split("\n")]
            parts.append("<p>" + "<br />".join(lines) + "</p>")
        doc = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">'
            '<head><title>' + heading + '</title>'
            '<link rel="stylesheet" type="text/css" href="style.css" /></head>'
            '<body><section><h1 id="start">' + heading + '</h1>' +
            "".join(parts) + "</section></body></html>"
        )
        chapter_files.append(("OEBPS/" + name, doc))
        nav_items.append('<li><a href="' + name + '#start">' + heading + '</a></li>')
        opf_items.append(
            '<item id="c' + str(idx) + '" href="' + name +
            '" media-type="application/xhtml+xml"/>')
        spine_items.append('<itemref idref="c' + str(idx) + '"/>')
    cover_art = book.get("cover")
    cover_image = (
        '<p class="cover"><img src="cover.jpg" alt="Author-supplied cover artwork" /></p>'
        if cover_art else ''
    )
    cover = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">'
        '<head><title>' + title + '</title></head><body>'
        '<section>' + cover_image + '<h1>' + title + '</h1>' +
        ('<p class="byline">' + author + '</p>' if author else '') +
        '</section></body></html>'
    )
    nav = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops">'
        '<head><title>Contents</title></head><body>'
        '<nav epub:type="toc" id="toc"><h2>Contents</h2><ol>' +
        "".join(nav_items) + "</ol></nav></body></html>"
    )
    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="uid" xml:lang="en">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:identifier id="uid">' + uid + '</dc:identifier>'
        '<dc:title>' + title + '</dc:title>'
        '<dc:language>en</dc:language><dc:creator>' + author + '</dc:creator>'
        '<meta property="dcterms:modified">' + now + '</meta></metadata>'
        '<manifest>'
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="cover" href="title.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="css" href="style.css" media-type="text/css"/>' +
        ('<item id="coverimg" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>'
         if cover_art else '') +
        "".join(opf_items) + '</manifest>'
        '<spine><itemref idref="cover"/>' +
        "".join(spine_items) + '</spine></package>'
    )
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/package.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    css = (
        'body{font-family:serif;line-height:1.55;margin:1em}'
        'h1{text-align:center;font-size:1.6em;margin:1.6em 0 1em}'
        'p{margin:0 0 1em;text-indent:.9em}'
        '.byline{text-align:center;text-indent:0;margin:2em 0}'
        '.cover{text-align:center;text-indent:0;margin:1em 0}'
        '.cover img{max-width:100%;max-height:80vh;object-fit:contain}'
    )
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as z:
        z.writestr("mimetype", b"application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        for name, data in [
            ("META-INF/container.xml", container),
            ("OEBPS/package.opf", opf),
            ("OEBPS/nav.xhtml", nav),
            ("OEBPS/title.xhtml", cover),
            ("OEBPS/style.css", css),
        ] + chapter_files:
            z.writestr(name, data.encode("utf-8"),
                       compress_type=zipfile.ZIP_DEFLATED)
        if cover_art:
            z.writestr("OEBPS/cover.jpg", cover_art["jpeg"],
                       compress_type=zipfile.ZIP_STORED)
    return content.getvalue()


def build_book_export(book: Dict[str, Any], fmt: str) -> Dict[str, Any]:
    if fmt not in MIMES:
        raise ValueError("Choose DOCX, EPUB or PDF for the assembled book.")
    if not isinstance(book, dict) or not isinstance(book.get("chapters"), list):
        raise ValueError("Verified assembled chapter data is required.")
    if not book["chapters"]:
        raise ValueError("An assembled book needs at least one chapter.")
    for text in [book["title"], book["author"]] + [
            val for c in book["chapters"] for val in (c["title"], c["text"])]:
        _safe_xml(text)
    if fmt == "docx":
        body = _docx_book(book)
    elif fmt == "epub":
        body = _epub_book(book)
    else:
        body = make_pdf(
            book["title"], book["author"], book["chapters"],
            cover=book.get("cover")
        )
    return {
        "ok": True, "body": body,
        "content_type": MIMES[fmt],
        "filename": _filename(book["title"], fmt),
        "source_unchanged": True, "saved": False,
    }
