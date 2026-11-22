"""Author-controlled series/book/act planning overlay for Story Forge projects.

Additive metadata only. No changes to existing project, chapter, draft, canon,
or manuscript formats. Every change requires the current revision and is backed
up before overwrite. Acts use stable IDs so renames retain scene references.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from pathlib import Path
from typing import Any, Dict

from .storage import Store, contained, jwrite, now

SCHEMA = "kayock.writer.series_outline.v1"


class SeriesOutline:
    def __init__(self, store: Store, storyforge):
        self.store, self.storyforge = store, storyforge
        self._lock = threading.RLock()

    def _scope(self, project_id: str):
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("Choose an existing Story Forge project.")
        manifest = self.storyforge.load_manifest(project_id)
        if not isinstance(manifest, dict) or not manifest.get("project_id"):
            raise ValueError("Story Forge project not found.")
        project = str(manifest["project_id"])
        root = self.storyforge.project_root(project)
        if root is None or not root.is_dir():
            raise ValueError("Story Forge project directory is missing.")
        file = root / "Planning" / "series_outline.json"
        if not contained(file, root) or file.is_symlink():
            raise ValueError("Unsafe series outline path.")
        book_ids = [
            book["id"] for book in manifest.get("books", [])
            if isinstance(book, dict) and isinstance(book.get("id"), str)
        ]
        return project, book_ids, file

    @staticmethod
    def _revision(raw: bytes):
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _empty(project: str):
        return {"schema": SCHEMA, "project_id": project,
                "series_title": "", "series_notes": "",
                "acts": [], "modified": ""}

    def _load(self, project, book_ids, file):
        if not file.exists():
            obj = self._empty(project)
            raw = json.dumps(obj, sort_keys=True).encode("utf-8")
            return obj, self._revision(raw)
        try:
            raw = file.read_bytes()
            obj = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("Series outline is damaged; refusing to overwrite.") from exc
        if (not isinstance(obj, dict) or obj.get("schema") != SCHEMA
                or obj.get("project_id") != project
                or not isinstance(obj.get("series_title"), str)
                or len(obj["series_title"]) > 160
                or not isinstance(obj.get("series_notes"), str)
                or len(obj["series_notes"]) > 6000
                or not isinstance(obj.get("acts"), list)
                or len(obj["acts"]) > 240):
            raise ValueError("Series outline has an unsupported schema.")
        ids = set()
        for act in obj["acts"]:
            if (not isinstance(act, dict)
                    or not isinstance(act.get("id"), str)
                    or len(act["id"]) != 32
                    or any(c not in "0123456789abcdef" for c in act["id"])
                    or act["id"] in ids
                    or act.get("book_id") not in book_ids
                    or not isinstance(act.get("title"), str)
                    or not act["title"].strip() or len(act["title"]) > 140
                    or not isinstance(act.get("summary"), str)
                    or len(act["summary"]) > 3000):
                raise ValueError("Series outline has invalid or orphaned acts.")
            ids.add(act["id"])
        return obj, self._revision(raw)

    def read(self, project_id: str) -> Dict[str, Any]:
        with self._lock:
            project, books, file = self._scope(project_id)
            obj, rev = self._load(project, books, file)
            return {"ok": True, "outline": obj, "revision": rev,
                    "available_books": books, "read_only": True,
                    "note": "Series/act planning never modifies existing Story Forge project or manuscript records."}

    def change(self, payload: dict) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Series outline change must be an object.")
        with self._lock:
            project, books, file = self._scope(payload.get("project_id"))
            obj, rev = self._load(project, books, file)
            if payload.get("expected_revision") != rev:
                raise ValueError("Series outline changed since it was loaded. Refresh before saving.")
            action = payload.get("action")
            if action == "details":
                title, notes = payload.get("series_title"), payload.get("series_notes")
                if (not isinstance(title, str) or len(title) > 160
                        or not isinstance(notes, str) or len(notes) > 6000):
                    raise ValueError("Series title and notes are invalid.")
                obj["series_title"] = title.strip()
                obj["series_notes"] = notes.strip()
            elif action == "act_add":
                book_id = payload.get("book_id")
                title = payload.get("title")
                summary = payload.get("summary", "")
                if book_id not in books:
                    raise ValueError("Act must belong to an existing book.")
                if (not isinstance(title, str) or not title.strip() or len(title) > 140
                        or not isinstance(summary, str) or len(summary) > 3000):
                    raise ValueError("Act title or summary is invalid.")
                if len(obj["acts"]) >= 240:
                    raise ValueError("Maximum 240 acts in one series outline.")
                obj["acts"].append({
                    "id": uuid.uuid4().hex, "book_id": book_id,
                    "title": title.strip(), "summary": summary.strip(),
                    "created": now()
                })
            elif action == "act_edit":
                act_id = payload.get("act_id")
                act = next((a for a in obj["acts"] if a["id"] == act_id), None)
                if act is None:
                    raise ValueError("Act not found.")
                title, summary = payload.get("title"), payload.get("summary")
                if (not isinstance(title, str) or not title.strip() or len(title) > 140
                        or not isinstance(summary, str) or len(summary) > 3000):
                    raise ValueError("Act title or summary is invalid.")
                act["title"] = title.strip()
                act["summary"] = summary.strip()
                # No act deletion or cross-book moving in this phase.
            else:
                raise ValueError("Supported series changes: details, act_add, act_edit.")
            obj["modified"] = now()
            if file.exists() and self.store.backup_file(file, kind="series_outlines") is None:
                raise ValueError("Cannot back up current outline; no changes made.")
            jwrite(file, obj)
            return {"ok": True, "outline": obj,
                    "revision": self._revision(file.read_bytes()),
                    "manuscript_unchanged": True,
                    "message": "Series outline saved; existing books and manuscripts unchanged."}
