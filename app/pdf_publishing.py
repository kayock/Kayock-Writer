"""Simple, searchable, paginate-on-write PDF generation (Python stdlib only).

This deliberately conservative PDF edition uses embedded PDF Base-14 Courier
fonts and Windows-1252 encoding. It REFUSES unsupported characters instead of
silently replacing or transliterating the author's words. DOCX / EPUB preserve
full XML-supported Unicode and should be used for broader scripts.
"""
from __future__ import annotations

import io
import textwrap
from typing import Dict, List

PAGE_W, PAGE_H = 612, 792
LEFT, RIGHT, TOP, BOTTOM = 72, 72, 70, 72
BODY_SIZE = 10.5
BODY_LEADING = 15
MAX_BODY_WIDTH = PAGE_W - LEFT - RIGHT
BODY_CHARS = int(MAX_BODY_WIDTH // (BODY_SIZE * 0.6))


def _pdf_chars(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("PDF text must be a string.")
    if any(ord(ch) < 32 and ch not in "\n\t\r" for ch in value):
        raise ValueError("PDF text includes an unsupported control character.")
    try:
        value.encode("cp1252")
    except UnicodeEncodeError as exc:
        char = value[exc.start]
        raise ValueError(
            "This basic PDF font cannot represent " + repr(char) +
            " (U+%04X). Export DOCX/EPUB for full Unicode; no characters were replaced." %
            ord(char)
        ) from exc
    return value


def _text(value: str, x: float, y: float, font: str, size: float) -> bytes:
    raw = _pdf_chars(value).encode("cp1252")
    return (
        "BT /" + font + " " + str(size) + " Tf " +
        "1 0 0 1 %.2f %.2f Tm " % (x, y)
    ).encode("ascii") + b"<" + raw.hex().upper().encode("ascii") + b"> Tj ET\n"


def _wrap(text: str, limit: int) -> List[str]:
    if not text:
        return [""]
    lines = []
    for line in text.expandtabs(4).split("\n"):
        if not line:
            lines.append("")
        else:
            lines.extend(textwrap.wrap(
                line, width=limit, break_long_words=True,
                break_on_hyphens=False,
                replace_whitespace=False, drop_whitespace=False,
            ))
    return lines


def make_pdf(title: str, author: str, chapters: List[Dict[str, str]]) -> bytes:
    if not chapters:
        raise ValueError("PDF needs at least one passage.")
    for item in (title, author):
        _pdf_chars(item)
    for c in chapters:
        _pdf_chars(c["title"])
        _pdf_chars(c["text"])

    pages: List[List[bytes]] = [[]]
    title_lines = _wrap(title, 40)
    for i, line in enumerate(title_lines):
        size = 18
        # Courier-Bold: glyph advance = 0.6*point size.
        pages[0].append(_text(line, max(LEFT, (PAGE_W - len(line)*size*.6)/2),
                              475-i*26, "F2", size))
    if author:
        pages[0].append(_text(author, max(LEFT,(PAGE_W-len(author)*12*.6)/2),
                              390-len(title_lines)*5,"F1",12))

    for chapter in chapters:
        # Every new chapter starts on a new page, never overwriting the source.
        page: List[bytes] = []
        pages.append(page)
        y = PAGE_H - TOP
        for line in _wrap(chapter["title"], 50):
            page.append(_text(line, LEFT, y, "F2", 14))
            y -= 23
        y -= 25
        for paragraph in chapter["text"].replace("\r\n","\n").replace("\r","\n").split("\n\n"):
            for line in _wrap(paragraph, BODY_CHARS):
                if y < BOTTOM+15:
                    page = []
                    pages.append(page)
                    y = PAGE_H - TOP
                if line:
                    page.append(_text(line, LEFT, y, "F1", BODY_SIZE))
                y -= BODY_LEADING
            y -= 9
    for number, page in enumerate(pages, start=1):
        # Footer is not placed near body text. Page 1 is the title page.
        page.append(_text(str(number), PAGE_W/2-4, 43, "F1", 9))

    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>",
    }
    kids = []
    for i, page in enumerate(pages):
        page_id, stream_id = 5+2*i, 6+2*i
        kids.append(str(page_id) + " 0 R")
        stream = b"".join(page)
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            "/Contents " + str(stream_id) + " 0 R >>"
        ).encode("ascii")
        objects[stream_id] = (
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" +
            stream + b"endstream"
        )
    objects[2] = (
        "<< /Type /Pages /Kids [" + " ".join(kids) + "] /Count " + str(len(pages)) + " >>"
    ).encode("ascii")
    result = io.BytesIO()
    result.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, max(objects)+1):
        offsets.append(result.tell())
        result.write(str(object_id).encode("ascii") + b" 0 obj\n")
        result.write(objects[object_id])
        result.write(b"\nendobj\n")
    xref_at = result.tell()
    result.write(("xref\n0 %d\n" % (len(offsets))).encode("ascii"))
    result.write(b"0000000000 65535 f \n")
    for at in offsets[1:]:
        result.write(("%010d 00000 n \n" % at).encode("ascii"))
    result.write((
        "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(offsets), xref_at)
    ).encode("ascii"))
    return result.getvalue()
