"""Read-only Story Forge book assembly from explicitly selected, verified draft versions.

No manuscript is opened except the author's selected saved chapter versions.
No draft, project, book, scene board, or Story Bible is modified. The preview
token invalidates when chapter files, selections, or draft history change.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from .storage import contained, slug
from .cover_art import decode_cover
from .unicode_pdf import decode_font

MAX_CHAPTERS = 160
MAX_CHARS = 800_000
MAX_FILE_BYTES = 360_000


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BookAssembler:
    def __init__(self, storyforge):
        self.forge = storyforge
        self._lock = threading.RLock()

    def _scope(self, project_id, book_id):
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("Choose a saved Story Forge project.")
        if not isinstance(book_id, str) or not book_id.strip():
            raise ValueError("Choose a book in that project.")
        manifest = self.forge.load_manifest(project_id)
        if not isinstance(manifest, dict) or not manifest.get("project_id"):
            raise ValueError("Story Forge project does not exist.")
        selected = next((b for b in manifest.get("books", [])
                         if isinstance(b, dict) and b.get("id") == book_id), None)
        if selected is None:
            raise ValueError("Book is not listed in the selected project.")
        root = self.forge.project_root(manifest["project_id"])
        if root is None or not root.is_dir():
            raise ValueError("Project directory not found.")
        # Source draft paths match Story Forge's existing exact book naming.
        base = root / "Drafts" / slug(book_id).lower()
        manifest_path = base / "draft_manifest.json"
        if (not contained(manifest_path, root) or manifest_path.is_symlink()
                or not manifest_path.is_file()):
            raise ValueError("Saved draft history is missing or unsafe.")
        raw = manifest_path.read_bytes()
        if len(raw) > 3_000_000:
            raise ValueError("Draft manifest exceeds book assembly limit.")
        try:
            history = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Draft history is damaged; no content was assembled.") from exc
        if not isinstance(history, dict) or not isinstance(history.get("versions"), list):
            raise ValueError("Draft history format is incompatible.")
        if len(history["versions"]) > 10000:
            raise ValueError("Draft history contains too many versions for this assembler.")
        return manifest["project_id"], selected, base, raw, history["versions"]

    @staticmethod
    def _entries(history):
        result = {}
        for e in history:
            if not isinstance(e, dict):
                raise ValueError("Invalid record in saved draft history.")
            chapter = e.get("chapter")
            filename = e.get("filename")
            digest = e.get("content_sha256")
            if (not isinstance(chapter, str) or not chapter.strip()
                    or len(chapter) > 200 or not isinstance(filename, str)
                    or not filename.endswith(".md") or Path(filename).name != filename
                    or "/" in filename or "\\" in filename
                    or not isinstance(digest, str) or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)):
                raise ValueError("Saved draft history contains an invalid reference.")
            result[(chapter, filename)] = e
        return result

    def options(self, project_id, book_id):
        with self._lock:
            project, book, _, _, history = self._scope(project_id, book_id)
            by_chapter = {}
            entries = self._entries(history)
            for (chapter, filename), record in entries.items():
                group = by_chapter.setdefault(chapter, [])
                group.append({
                    "filename": filename, "version": record.get("version"),
                    "word_count": record.get("word_count", 0),
                })
            groups = [
                {"chapter": name, "versions": versions,
                 "latest_filename": versions[-1]["filename"]}
                for name, versions in by_chapter.items()
            ]
            return {
                "ok": True, "project_id": project, "book_id": book_id,
                "book_title": str(book.get("title") or book_id),
                "chapters": groups, "read_only": True,
                "note": "Every version comes from the saved history. Select the chapters and order before preview.",
            }

    def _assemble(self, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError("Book assembly request must be an object.")
        project, book, base, history_raw, history = self._scope(
            payload.get("project_id"), payload.get("book_id"))
        selected = payload.get("chapters")
        if (not isinstance(selected, list) or not 1 <= len(selected) <= MAX_CHAPTERS):
            raise ValueError("Select 1–160 chapters in the desired reading order.")
        title = payload.get("title", str(book.get("title") or "Untitled Book"))
        author = payload.get("author", "")
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ValueError("A book title up to 200 characters is required.")
        if not isinstance(author, str) or len(author) > 160:
            raise ValueError("Author must be text up to 160 characters.")
        cover = decode_cover(payload.get("cover_jpeg_base64"))
        unicode_font = decode_font(payload.get("pdf_ttf_base64"))
        index = self._entries(history)
        used = set()
        chapters: List[Dict[str, Any]] = []
        identity = []
        total = 0
        for row in selected:
            if not isinstance(row, dict) or set(row) != {"chapter", "filename"}:
                raise ValueError("Each selection must have a chapter and saved filename.")
            chapter, filename = row["chapter"], row["filename"]
            if not isinstance(chapter, str) or not isinstance(filename, str):
                raise ValueError("Invalid saved chapter selection.")
            pair = (chapter, filename)
            if pair in used:
                raise ValueError("A saved chapter cannot be selected twice.")
            if any(existing["title"] == chapter for existing in chapters):
                raise ValueError("Choose only one saved version of each chapter.")
            used.add(pair)
            record = index.get(pair)
            if record is None:
                raise ValueError("Selected version is absent from Story Forge history.")
            path = base / filename
            if (not contained(path, base) or path.is_symlink()
                    or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES):
                raise ValueError("Saved chapter file is missing or unsafe.")
            raw = path.read_bytes()
            if len(raw) > MAX_FILE_BYTES:
                raise ValueError("Chapter is too large for book assembly.")
            try:
                content = self.forge._draft_body(raw.decode("utf-8"))
            except (UnicodeError, ValueError) as exc:
                raise ValueError("Saved chapter is not readable UTF-8 text.") from exc
            if not content.strip():
                raise ValueError("An empty saved chapter cannot be assembled.")
            if _hash(content.encode("utf-8")) != record["content_sha256"]:
                raise ValueError("Saved chapter differs from its version history; no export created.")
            total += len(content)
            if total > MAX_CHARS:
                raise ValueError("Selected book exceeds 800,000 characters; no text was truncated.")
            chapters.append({
                "title": chapter, "text": content,
                "filename": filename, "version": record.get("version"),
                "sha256": _hash(content.encode("utf-8")),
                "words": len(content.split())
            })
            identity.append({
                "chapter": chapter, "filename": filename,
                "file_hash": _hash(raw),
                "content_hash": chapters[-1]["sha256"],
            })
        canonical = json.dumps({
            "schema": "kayock.writer.assembled_book.v1",
            "project": project, "book": payload["book_id"],
            "title": title, "author": author,
            "manifest_sha256": _hash(history_raw), "ordered_selections": identity,
            "cover_sha256": cover["sha256"] if cover else "",
            "pdf_font_sha256": unicode_font["sha256"] if unicode_font else "",
        }, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        token = _hash(canonical)
        return {
            "title": title, "author": author, "writing_type": "novel",
            "chapters": chapters, "token": token, "cover": cover,
            "pdf_font": unicode_font,
            "project_id": project, "book_id": payload["book_id"],
            "book_title": str(book.get("title") or payload["book_id"]),
        }

    def preview(self, payload: Dict[str, Any]):
        with self._lock:
            book = self._assemble(payload)
            return {
                "ok": True, "project_id": book["project_id"], "book_id": book["book_id"],
                "title": book["title"], "author": book["author"],
                "confirmation_token": book["token"],
                "chapter_count": len(book["chapters"]),
                "total_words": sum(c["words"] for c in book["chapters"]),
                "unicode_pdf_font_present": book["pdf_font"] is not None,
                "unicode_pdf_font_size": (
                    book["pdf_font"]["size"] if book["pdf_font"] else 0
                ),
                "cover_present": book["cover"] is not None,
                "cover_size": book["cover"]["size"] if book["cover"] else 0,
                "cover_dimensions": (
                    [book["cover"]["width"], book["cover"]["height"]]
                    if book["cover"] else None
                ),
                "chapters": [
                    {"title": c["title"], "filename": c["filename"],
                     "version": c["version"], "words": c["words"],
                     "excerpt": c["text"][:170]}
                    for c in book["chapters"]
                ],
                "read_only": True, "source_unchanged": True,
                "message": "Assembly preview only. No existing writing or project files changed.",
            }

    def verified_book(self, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError("Invalid export request.")
        token = payload.get("confirmation_token")
        if not isinstance(token, str) or len(token) != 64:
            raise ValueError("Preview the selected chapters before exporting.")
        with self._lock:
            book = self._assemble(payload)
            if book["token"] != token:
                raise ValueError("Chapter choices, saved text or history changed since preview. Preview again.")
            return book
