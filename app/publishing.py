"""In-memory, local manuscript exports: DOCX and EPUB 3, no new dependencies.

Exports are generated from explicit Finishing Desk text only; never read, edit,
publish, send, or implicitly select a user's existing manuscript on disk.
This is a simple single-document edition, not a full print-layout engine.
"""
from __future__ import annotations

import html
import io
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List
from xml.sax.saxutils import escape

MIMES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "epub": "application/epub+zip",
    "pdf": "application/pdf",
}

def _safe_xml(value: str) -> str:
    """Fail rather than silently changing the writer's characters."""
    if any(
        (ord(ch) < 32 and ch not in "\t\n\r")
        or 0xD800 <= ord(ch) <= 0xDFFF
        or ord(ch) in (0xFFFE, 0xFFFF)
        for ch in value
    ):
        raise ValueError("Manuscript contains characters invalid in XML; no file was generated.")
    return value


def _source(payload: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Export input must be a JSON object.")
    title, author, text = payload.get("title"), payload.get("author"), payload.get("text")
    writing_type = payload.get("writing_type", "prose")
    fmt = payload.get("format")
    if fmt not in MIMES:
        raise ValueError("Choose DOCX, EPUB or PDF format.")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("A title up to 200 characters is required.")
    if not isinstance(author, str) or len(author) > 160:
        raise ValueError("Author must be text up to 160 characters.")
    if not isinstance(text, str) or not text.strip() or len(text) > 80000:
        raise ValueError("Export text must be 1–80,000 characters; no excerpt is silently truncated.")
    if writing_type not in ("poem", "short_story", "novel", "prose"):
        raise ValueError("Unsupported writing type.")
    title, author = title.strip(), author.strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for part in (title, author, text):
        _safe_xml(part)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", title)[:80].strip("_") or "Kayock_Writing"
    return {"title": title, "author": author, "text": text,
            "writing_type": writing_type, "format": fmt, "filename": safe + "." + fmt}


def _paragraphs(text: str) -> List[str]:
    # Separate prose paragraphs and poetry stanzas; preserve explicit lines.
    return re.split(r"\n[ \t]*\n", text)


def _docx_paragraph(text: str, style: str = "") -> str:
    style_xml = (f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else
                 '<w:pPr><w:spacing w:after="160"/></w:pPr>')
    lines = text.split("\n")
    runs = []
    for i, line in enumerate(lines):
        if i:
            runs.append('<w:r><w:br/></w:r>')
        if line:
            runs.append('<w:r><w:t xml:space="preserve">' + escape(line) + '</w:t></w:r>')
        else:
            runs.append('<w:r><w:t></w:t></w:r>')
    return '<w:p>' + style_xml + ''.join(runs) + '</w:p>'


def _docx(source: Dict[str, str]) -> bytes:
    paragraphs = [_docx_paragraph(source["title"], "Title")]
    if source["author"]:
        paragraphs.append(_docx_paragraph(source["author"], "Subtitle"))
    paragraphs.extend(_docx_paragraph(part) for part in _paragraphs(source["text"]))
    body = ''.join(paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + body +
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1152" w:right="1152" w:bottom="1152" w:left="1152"/>'
        '</w:sectPr></w:body></w:document>'
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/>'
        '<w:sz w:val="24"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
        '<w:pPr><w:spacing w:after="220"/><w:jc w:val="center"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/>'
        '<w:pPr><w:spacing w:after="320"/><w:jc w:val="center"/></w:pPr>'
        '<w:rPr><w:sz w:val="22"/></w:rPr></w:style>'
        '</w:styles>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>'
    )
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in (
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", rels),
            ("word/document.xml", document),
            ("word/styles.xml", styles),
            ("word/_rels/document.xml.rels", doc_rels),
        ):
            z.writestr(name, value.encode("utf-8"))
    return payload.getvalue()


def _epub(source: Dict[str, str]) -> bytes:
    title, author, body = (html.escape(source[k], quote=True)
                           for k in ("title", "author", "text"))
    book_id = "urn:uuid:" + str(uuid.uuid4())
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    paragraphs = []
    for part in _paragraphs(source["text"]):
        escaped_lines = [html.escape(line, quote=True) for line in part.split("\n")]
        cls = ' class="stanza"' if source["writing_type"] == "poem" else ""
        paragraphs.append("<p" + cls + ">" + "<br />".join(escaped_lines) + "</p>")
    chapter = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">'
        '<head><title>' + title + '</title><meta charset="UTF-8" />'
        '<link rel="stylesheet" type="text/css" href="style.css" /></head><body>'
        '<section epub:type="chapter" xmlns:epub="http://www.idpf.org/2007/ops">'
        '<h1 id="start">' + title + '</h1>' +
        ('<p class="byline">' + author + '</p>' if author else '') +
        ''.join(paragraphs) + '</section></body></html>'
    )
    nav = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
        '<head><title>Contents</title></head><body>'
        '<nav epub:type="toc" id="toc"><h2>Contents</h2><ol>'
        '<li><a href="chapter.xhtml#start">' + title + '</a></li>'
        '</ol></nav></body></html>'
    )
    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="uid" xml:lang="en">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:identifier id="uid">' + book_id + '</dc:identifier>'
        '<dc:title>' + title + '</dc:title>'
        '<dc:language>en</dc:language>'
        '<dc:creator>' + author + '</dc:creator>'
        '<meta property="dcterms:modified">' + updated + '</meta></metadata>'
        '<manifest>'
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="css" href="style.css" media-type="text/css"/>'
        '</manifest><spine><itemref idref="chapter"/></spine></package>'
    )
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/package.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    css = (
        'body{font-family:serif;line-height:1.55;margin:1em;}'
        'h1{text-align:center;font-size:1.7em;margin:1.8em 0 1em;}'
        'p{margin:0 0 1em;text-indent:0.8em;}'
        'p.stanza{margin:0 0 1.3em;text-indent:0;}'
        'p.byline{text-align:center;text-indent:0;margin-bottom:2em;}'
    )
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as z:
        # EPUB specification requires first entry uncompressed.
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name, value in (
            ("META-INF/container.xml", container),
            ("OEBPS/package.opf", opf),
            ("OEBPS/nav.xhtml", nav),
            ("OEBPS/chapter.xhtml", chapter),
            ("OEBPS/style.css", css),
        ):
            z.writestr(name, value.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
    return payload.getvalue()


def build_export(payload: Dict[str, Any]) -> Dict[str, Any]:
    source = _source(payload)
    if source["format"] == "docx":
        content = _docx(source)
    elif source["format"] == "epub":
        content = _epub(source)
    else:
        from .pdf_publishing import make_pdf
        content = make_pdf(
            source["title"], source["author"],
            [{"title": source["title"], "text": source["text"]}]
        )
    return {
        "ok": True, "filename": source["filename"],
        "content_type": MIMES[source["format"]], "body": content,
        "saved": False, "source_unchanged": True,
    }
