"""Opt-in Unicode PDF rendering with an author-provided TrueType font.

Uses Python's standard library, and never searches for, stores or bundles
font files. Embeds only the specifically uploaded .ttf in the output PDF.
Simple direct glyph positioning: no bidirectional layout, advanced shaping,
ligatures, color-emoji rendering or font fallback. Missing glyphs are errors,
not silent replacements. The built-in Windows-1252 PDF remains the default.
"""
from __future__ import annotations

import base64
import binascii
import bisect
import hashlib
import io
import struct
from typing import Any, Dict, List

MAX_TTF_BYTES = 3 * 1024 * 1024
MAX_GLYPHS_USED = 8192

def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]

def _s16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">h", data, offset)[0]

def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


class TrueTypeFont:
    def __init__(self, data: bytes):
        if (not isinstance(data, bytes) or not 512 <= len(data) <= MAX_TTF_BYTES
                or data[:4] not in (b"\0\1\0\0", b"true")):
            raise ValueError("Select a valid TrueType .ttf file up to 3 MB (not OTF/CFF/TTC).")
        n = _u16(data, 4)
        if not 1 <= n <= 256 or len(data) < 12 + n * 16:
            raise ValueError("TrueType font table directory is invalid.")
        tables = {}
        for idx in range(n):
            p = 12 + idx * 16
            tag = data[p:p + 4].decode("latin-1")
            offset, length = _u32(data, p + 8), _u32(data, p + 12)
            if (offset > len(data) or length > len(data)
                    or offset + length > len(data) or tag in tables):
                raise ValueError("TrueType font has invalid table offsets.")
            tables[tag] = (offset, length)
        for tag in ("head", "hhea", "hmtx", "maxp", "cmap", "glyf", "loca"):
            if tag not in tables:
                raise ValueError("TrueType font is missing the required " + tag + " table.")
        self.data, self.tables = data, tables
        self._require("head", 54)
        self._require("hhea", 36)
        self._require("maxp", 6)
        self.units = _u16(data, self._at("head") + 18)
        self.num_glyphs = _u16(data, self._at("maxp") + 4)
        self.num_metrics = _u16(data, self._at("hhea") + 34)
        if (not 16 <= self.units <= 16384 or not 1 <= self.num_glyphs <= 65535
                or not 1 <= self.num_metrics <= self.num_glyphs):
            raise ValueError("TrueType font metrics are invalid.")
        self._require("hmtx", 4 * self.num_metrics)
        self.bbox = tuple(_s16(data, self._at("head") + i) for i in (36, 38, 40, 42))
        self.ascent = _s16(data, self._at("hhea") + 4)
        self.descent = _s16(data, self._at("hhea") + 6)
        self._cmap = self._choose_cmap()

    def _at(self, name: str) -> int:
        return self.tables[name][0]

    def _require(self, name: str, count: int):
        if self.tables[name][1] < count:
            raise ValueError("TrueType " + name + " table is truncated.")

    def _choose_cmap(self):
        base, length = self.tables["cmap"]
        if length < 4:
            raise ValueError("TrueType cmap table is truncated.")
        count = _u16(self.data, base + 2)
        if count > 256 or length < 4 + count * 8:
            raise ValueError("TrueType cmap directory is damaged.")
        options = []
        for idx in range(count):
            off = base + 4 + idx * 8
            platform, encoding, cmap_relative = (
                _u16(self.data, off), _u16(self.data, off + 2),
                _u32(self.data, off + 4)
            )
            pos = base + cmap_relative
            if pos + 8 > base + length:
                continue
            fmt = _u16(self.data, pos)
            if fmt not in (4, 12):
                continue
            if platform not in (0, 3) or (platform == 3 and encoding not in (1, 10)):
                continue
            if fmt == 12:
                if pos + 16 > base + length:
                    continue
                size = _u32(self.data, pos + 4)
                groups = _u32(self.data, pos + 12)
                if (groups > 65536 or size < 16 or pos + size > base + length
                        or 16 + groups * 12 > size):
                    continue
                starts, ranges = [], []
                for j in range(groups):
                    at = pos + 16 + j * 12
                    start, end, gid = (_u32(self.data, at), _u32(self.data, at + 4),
                                       _u32(self.data, at + 8))
                    if (start > end or end > 0x10FFFF
                            or (starts and start <= ranges[-1][1])):
                        raise ValueError("TrueType Unicode cmap groups overlap.")
                    starts.append(start)
                    ranges.append((start, end, gid))
                options.append((3, ("12", starts, ranges)))
            else:
                size = _u16(self.data, pos + 2)
                if size < 24 or pos + size > base + length:
                    continue
                seg_count = _u16(self.data, pos + 6) // 2
                if not seg_count or 16 + 8 * seg_count > size:
                    continue
                options.append((2, ("4", pos, size, seg_count)))
        if not options:
            raise ValueError("TrueType font has no supported Unicode cmap (format 4/12).")
        return sorted(options, key=lambda item: item[0], reverse=True)[0][1]

    def glyph(self, scalar: int) -> int:
        mode = self._cmap[0]
        if mode == "12":
            starts, groups = self._cmap[1:]
            i = bisect.bisect_right(starts, scalar) - 1
            if i < 0 or scalar > groups[i][1]:
                return 0
            result = groups[i][2] + scalar - groups[i][0]
        else:
            if scalar > 0xFFFF:
                return 0
            _, pos, length, count = self._cmap
            ends_at = pos + 14
            starts_at = ends_at + count * 2 + 2
            delta_at = starts_at + count * 2
            ranges_at = delta_at + count * 2
            ends = [_u16(self.data, ends_at + j * 2) for j in range(count)]
            i = bisect.bisect_left(ends, scalar)
            if i >= count or scalar < _u16(self.data, starts_at + i * 2):
                return 0
            delta = _s16(self.data, delta_at + i * 2)
            range_offset = _u16(self.data, ranges_at + i * 2)
            if range_offset == 0:
                result = (scalar + delta) & 0xFFFF
            else:
                off = ranges_at + i * 2 + range_offset + 2 * (
                    scalar - _u16(self.data, starts_at + i * 2)
                )
                if off + 2 > pos + length:
                    raise ValueError("TrueType cmap glyph offset is invalid.")
                result = _u16(self.data, off)
                if result:
                    result = (result + delta) & 0xFFFF
        if result >= self.num_glyphs:
            raise ValueError("TrueType cmap references an out-of-range glyph.")
        return result

    def width(self, glyph: int) -> int:
        idx = min(glyph, self.num_metrics - 1)
        return int(round(_u16(self.data, self._at("hmtx") + 4 * idx)
                         * 1000 / self.units))


def decode_font(value: Any) -> Dict[str, Any] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 4 * ((MAX_TTF_BYTES + 2) // 3):
        raise ValueError("Unicode PDF font exceeds the 3 MB .ttf limit.")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeError, ValueError, binascii.Error) as exc:
        raise ValueError("TrueType font is not valid base64 data.") from exc
    TrueTypeFont(raw)
    return {"raw": raw, "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw)}


class PdfFontRun:
    def __init__(self, font: TrueTypeFont):
        self.font = font
        self.cids: Dict[int, int] = {}
        self.gids = [0]
        self.scalars = [0]
        self.widths = [1000]

    def cid(self, character: str) -> int:
        scalar = ord(character)
        if scalar not in self.cids:
            if scalar in (0x0A, 0x0D, 0x09):
                raise ValueError("A PDF text run cannot contain a line break or tab.")
            if 0xD800 <= scalar <= 0xDFFF:
                raise ValueError("PDF text contains an invalid Unicode surrogate.")
            glyph = self.font.glyph(scalar)
            if glyph == 0:
                raise ValueError(
                    "Selected PDF font lacks glyph for " + repr(character) +
                    " (U+%04X). Choose another .ttf or export DOCX/EPUB." % scalar
                )
            if len(self.gids) > MAX_GLYPHS_USED:
                raise ValueError("Unicode PDF uses too many distinct glyphs.")
            assigned = len(self.gids)
            self.cids[scalar] = assigned
            self.gids.append(glyph)
            self.scalars.append(scalar)
            self.widths.append(self.font.width(glyph))
        return self.cids[scalar]

    def measure(self, text: str, size: float) -> float:
        return sum(self.widths[self.cid(ch)] * size / 1000 for ch in text)

    def put(self, text: str, x: float, y: float, size: float) -> bytes:
        glyphs = b"".join(self.cid(ch).to_bytes(2, "big") for ch in text)
        return (
            ("BT /F1 %g Tf 1 0 0 1 %.2f %.2f Tm <" % (size, x, y)).encode("ascii")
            + glyphs.hex().upper().encode("ascii") + b"> Tj ET\n"
        )

    def wrap(self, text: str, width: float, size: float) -> List[str]:
        lines = []
        for original in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = original.expandtabs(4)
            if not line:
                lines.append("")
                continue
            cursor = 0
            while cursor < len(line):
                start = cursor
                fitted_width = 0.0
                last_space = -1
                while cursor < len(line):
                    ch = line[cursor]
                    delta = self.widths[self.cid(ch)] * size / 1000
                    if fitted_width + delta > width:
                        break
                    fitted_width += delta
                    cursor += 1
                    if ch == " ":
                        last_space = cursor
                if cursor == start:
                    raise ValueError("A glyph is too wide for the selected page margins.")
                if cursor < len(line) and last_space > start:
                    cursor = last_space
                lines.append(line[start:cursor])
        return lines

    def to_unicode(self) -> bytes:
        header = (
            "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /KayockUnicode def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000><FFFF>\nendcodespacerange\n"
        )
        text = [header]
        for start in range(1, len(self.scalars), 100):
            count = min(100, len(self.scalars) - start)
            text.append(str(count) + " beginbfchar\n")
            for cid in range(start, start + count):
                utf16 = chr(self.scalars[cid]).encode("utf-16-be").hex().upper()
                text.append("<%04X><%s>\n" % (cid, utf16))
            text.append("endbfchar\n")
        text.append(
            "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
        )
        return "".join(text).encode("ascii")


def make_unicode_pdf(title: str, author: str, chapters: List[Dict[str, str]],
                     font_data: Dict[str, Any], cover=None) -> bytes:
    from .pdf_publishing import PAGE_W, PAGE_H, LEFT, TOP, BOTTOM, BODY_LEADING
    raw_font = font_data["raw"]
    font = TrueTypeFont(raw_font)
    run = PdfFontRun(font)
    for value in (title, author):
        if not isinstance(value, str):
            raise ValueError("PDF title and author must be text.")
    if not isinstance(chapters, list) or not chapters:
        raise ValueError("A Unicode PDF needs at least one chapter.")
    pages = [[]]
    title_y = 375 if cover else 475
    if cover:
        scale = min(405 / cover["width"], 305 / cover["height"])
        w, h = cover["width"] * scale, cover["height"] * scale
        pages[0].append(
            ("q %.3f 0 0 %.3f %.3f %.3f cm /Im1 Do Q\n"
             % (w, h, (PAGE_W-w)/2, 420)).encode("ascii")
        )
    title_lines = run.wrap(title, 460, 18)
    for i, line in enumerate(title_lines):
        x = max(LEFT, (PAGE_W - run.measure(line, 18)) / 2)
        pages[0].append(run.put(line, x, title_y-i*26, 18))
    if author:
        for i, line in enumerate(run.wrap(author, 460, 11)):
            x = max(LEFT, (PAGE_W-run.measure(line, 11))/2)
            pages[0].append(
                run.put(line, x, title_y-len(title_lines)*26-30-i*18, 11)
            )
    for chapter in chapters:
        heading, manuscript = chapter["title"], chapter["text"]
        if not isinstance(heading, str) or not isinstance(manuscript, str):
            raise ValueError("Chapter title and prose must be text.")
        page = []
        pages.append(page)
        y = PAGE_H - TOP
        for line in run.wrap(heading, 460, 14):
            page.append(run.put(line, LEFT, y, 14))
            y -= 23
        y -= 25
        for paragraph in manuscript.replace("\r\n","\n").replace("\r","\n").split("\n\n"):
            lines = run.wrap(paragraph, 468, 10.5)
            if len(lines) >= 2 and y-2*BODY_LEADING < BOTTOM+15:
                page=[];pages.append(page);y=PAGE_H-TOP
                for header in run.wrap(heading, 460, 9)[:1]:
                    page.append(run.put(header,LEFT,PAGE_H-44,9))
            for idx,line in enumerate(lines):
                remaining=len(lines)-idx
                if (y < BOTTOM+15 or
                        (remaining == 2 and y-BODY_LEADING < BOTTOM+15)):
                    page=[];pages.append(page);y=PAGE_H-TOP
                    for header in run.wrap(heading,460,9)[:1]:
                        page.append(run.put(header,LEFT,PAGE_H-44,9))
                if line:
                    page.append(run.put(line, LEFT, y, 10.5))
                y -= BODY_LEADING
            y -= 9
    for idx,page in enumerate(pages[1:],1):
        number=str(idx)
        page.append(run.put(number,(PAGE_W-run.measure(number,9))/2,43,9))

    # Object IDs: catalog=1, pages=2, type0 font=3, CIDFont=4,
    # descriptor=5, font stream=6, ToUnicode=7, CIDToGIDMap=8.
    objs = {}
    def stream_object(content: bytes, extra: str = "") -> bytes:
        return (
            ("<< /Length %d %s >>\nstream\n" % (len(content), extra)).encode("ascii")
            + content + b"\nendstream"
        )
    coords = lambda v: int(round(v * 1000 / font.units))
    bbox = [coords(v) for v in font.bbox]
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[3] = (
        "<< /Type /Font /Subtype /Type0 /BaseFont /KayockAuthorUnicode "
        "/Encoding /Identity-H /DescendantFonts [4 0 R] /ToUnicode 7 0 R >>"
    ).encode("ascii")
    glyph_widths = " ".join(str(w) for w in run.widths[1:])
    objs[4] = (
        "<< /Type /Font /Subtype /CIDFontType2 /BaseFont /KayockAuthorUnicode "
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
        "/FontDescriptor 5 0 R /DW 1000 /W [1 [" + glyph_widths +
        "]] /CIDToGIDMap 8 0 R >>"
    ).encode("ascii")
    objs[5] = (
        "<< /Type /FontDescriptor /FontName /KayockAuthorUnicode /Flags 32 "
        "/FontBBox ["+" ".join(map(str,bbox))+"] "
        "/ItalicAngle 0 /Ascent %d /Descent %d /CapHeight %d "
        "/StemV 80 /FontFile2 6 0 R >>"
        % (coords(font.ascent),coords(font.descent),coords(font.ascent))
    ).encode("ascii")
    objs[6] = stream_object(raw_font, "/Length1 "+str(len(raw_font)))
    objs[7] = stream_object(run.to_unicode())
    cmap_stream = b"".join(gid.to_bytes(2,"big") for gid in run.gids)
    objs[8] = stream_object(cmap_stream)

    kids = []
    cover_id = 9 + 2 * len(pages) if cover else None
    for idx,page in enumerate(pages):
        page_id, content_id = 9+idx*2, 10+idx*2
        kids.append(str(page_id)+" 0 R")
        extra = (" /XObject << /Im1 "+str(cover_id)+" 0 R >>"
                 if cover and idx==0 else "")
        objs[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 3 0 R >>"+extra+" >> "
            "/Contents "+str(content_id)+" 0 R >>"
        ).encode("ascii")
        objs[content_id] = stream_object(b"".join(page))
    if cover:
        image = cover["jpeg"]
        objs[cover_id] = stream_object(
            image,
            "/Type /XObject /Subtype /Image /Width "+str(cover["width"])+
            " /Height "+str(cover["height"])+
            " /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode"
        )
    objs[2] = (
        "<< /Type /Pages /Kids ["+" ".join(kids)+"] /Count "+
        str(len(pages))+" >>"
    ).encode("ascii")

    output=io.BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets=[0]
    for obj_id in range(1,max(objs)+1):
        offsets.append(output.tell())
        output.write(("%d 0 obj\n" % obj_id).encode("ascii"))
        output.write(objs[obj_id])
        output.write(b"\nendobj\n")
    startxref=output.tell()
    output.write(("xref\n0 %d\n" % len(offsets)).encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(("%010d 00000 n \n" % offset).encode("ascii"))
    output.write((
        "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(offsets),startxref)
    ).encode("ascii"))
    return output.getvalue()
