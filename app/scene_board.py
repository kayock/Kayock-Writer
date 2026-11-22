"""Manual, version-checked Story Forge scene corkboard.

An additive planning layer per existing project/book. Never edits, imports,
publishes, or deletes chapter cards, drafts, manuscripts or their manifests.
Writes are serialized and backed up. All changes require a fresh revision.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .storage import Store, contained, jwrite, now, slug
from .series_outline import SeriesOutline
from .draft_branches import DraftBranches

SCHEMA = "kayock.writer.scene_board.v1"
LANES = ("ideas", "outlined", "drafting", "revising", "ready", "parked")
FIELDS = ("title", "chapter", "summary", "pov", "location", "beats", "act_id", "draft_filename")
LIMITS = {"title": 160, "chapter": 160, "summary": 4000,
          "pov": 120, "location": 160, "beats": 6000,
          "act_id": 32, "draft_filename": 200}


class SceneBoard:
    def __init__(self, store: Store, storyforge):
        self.store, self.storyforge = store, storyforge
        self._lock = threading.RLock()
        self.outline = SeriesOutline(store, storyforge)
        self.branches = DraftBranches(store, storyforge)

    def _scope(self, project_id: str, book_id: str):
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("Choose a saved Story Forge project.")
        if not isinstance(book_id, str) or not book_id.strip():
            raise ValueError("Choose a book from this project.")
        manifest = self.storyforge.load_manifest(project_id)
        if not isinstance(manifest, dict) or not manifest.get("project_id"):
            raise ValueError("Story Forge project manifest not found.")
        project = str(manifest["project_id"])
        books = manifest.get("books") or []
        chosen = next((b for b in books if isinstance(b, dict)
                       and b.get("id") == book_id), None)
        if chosen is None:
            raise ValueError("Book is not listed in the selected project.")
        root = self.storyforge.project_root(project)
        if root is None or not root.is_dir():
            raise ValueError("Story Forge project directory is missing.")
        file = root / "Scenes" / "Boards" / (slug(book_id) + ".json")
        if not contained(file, root / "Scenes") or file.is_symlink():
            raise ValueError("Unsafe scene board path.")
        return project, book_id, file

    @staticmethod
    def _revision(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _empty(project: str, book: str) -> Dict[str, Any]:
        return {"schema": SCHEMA, "project_id": project,
                "book_id": book, "cards": [], "modified": ""}

    def _load(self, project: str, book: str, file: Path):
        if not file.exists():
            raw = json.dumps(self._empty(project, book), sort_keys=True).encode("utf-8")
            return self._empty(project, book), self._revision(raw)
        try:
            raw = file.read_bytes()
            data = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("Scene board JSON is damaged; refusing to overwrite.") from exc
        if (not isinstance(data, dict) or data.get("schema") != SCHEMA
                or data.get("project_id") != project or data.get("book_id") != book
                or not isinstance(data.get("cards"), list) or len(data["cards"]) > 2000):
            raise ValueError("Unsupported scene board format; refusing to overwrite.")
        ids = set()
        for card in data["cards"]:
            if (not isinstance(card, dict)
                    or not isinstance(card.get("id"), str)
                    or not card["id"].strip() or card["id"] in ids
                    or card.get("status") not in LANES):
                raise ValueError("Scene board card data is damaged; refusing to overwrite.")
            for key, maximum in LIMITS.items():
                # Older scene boards predate the act/draft reference fields.
                value = card.get(key, "") if key in ("act_id", "draft_filename") else card.get(key)
                if not isinstance(value, str) or len(value) > maximum:
                    raise ValueError("Scene board text field is damaged; refusing to overwrite.")
            ids.add(card["id"])
        return data, self._revision(raw)

    def read(self, project_id: str, book_id: str) -> Dict[str, Any]:
        with self._lock:
            project, book, path = self._scope(project_id, book_id)
            data, rev = self._load(project, book, path)
            for card in data["cards"]:
                card.setdefault("act_id", "")
                card.setdefault("draft_filename", "")
            # The board is annotated with verified links, but does not load
            # manuscript prose or alter any linked document.
            act_details = self.outline.read(project)["outline"]["acts"]
            names = {act["id"]: act["title"] for act in act_details
                     if act["book_id"] == book}
            for card in data["cards"]:
                card["act_title"] = names.get(card["act_id"], "")
                card["draft_valid"] = False
                if card["draft_filename"]:
                    try:
                        self.branches.verify_source(project, book,
                                                    card["draft_filename"],
                                                    card.get("chapter") or "")
                        card["draft_valid"] = True
                    except ValueError:
                        pass
            return {"ok": True, "board": data, "revision": rev,
                    "lanes": list(LANES), "acts": [
                        {"id": act["id"], "title": act["title"]}
                        for act in act_details if act["book_id"] == book
                    ],
                    "read_only": True,
                    "note": "Links are references only; scene board changes never edit linked chapter drafts."}

    @staticmethod
    def _clean(fields: Any, *, require_title: bool) -> Dict[str, str]:
        if not isinstance(fields, dict) or set(fields) - set(FIELDS):
            raise ValueError("Unrecognized scene card fields.")
        cleaned: Dict[str, str] = {}
        for key, value in fields.items():
            if not isinstance(value, str) or len(value) > LIMITS[key]:
                raise ValueError(key + " must be text of at most " + str(LIMITS[key]) + " characters.")
            cleaned[key] = value.strip()
        if require_title and not cleaned.get("title"):
            raise ValueError("Give the scene card a title.")
        return cleaned

    def _validate_links(self, project, book, chapter, fields):
        if "act_id" in fields and fields["act_id"]:
            acts = self.outline.read(project)["outline"]["acts"]
            if not any(a["id"] == fields["act_id"] and a["book_id"] == book
                       for a in acts):
                raise ValueError("Act does not belong to this book's series outline.")
        if "draft_filename" in fields and fields["draft_filename"]:
            self.branches.verify_source(project, book,
                                        fields["draft_filename"], chapter)

    def change(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Accept explicit add/update/move/park; never delete a card."""
        if not isinstance(payload, dict):
            raise ValueError("Scene change payload must be an object.")
        with self._lock:
            project, book, path = self._scope(payload.get("project_id"), payload.get("book_id"))
            data, revision = self._load(project, book, path)
            expected = payload.get("expected_revision")
            if not isinstance(expected, str) or expected != revision:
                raise ValueError("Scene board changed since it was loaded. Refresh before saving; no changes made.")
            action = payload.get("action")
            cards = data["cards"]
            card = None
            if action != "add":
                cid = payload.get("card_id")
                card = next((c for c in cards if c["id"] == cid), None)
                if card is None:
                    raise ValueError("Scene card not found. Refresh before editing.")
            if action == "add":
                if len(cards) >= 2000:
                    raise ValueError("Scene board reached its 2,000-card planning limit.")
                fields = self._clean(payload.get("fields"), require_title=True)
                self._validate_links(project, book, fields.get("chapter", ""), fields)
                status = payload.get("status", "ideas")
                if status not in LANES:
                    raise ValueError("Unknown scene lane.")
                card = {"id": uuid.uuid4().hex,
                        **{name: fields.get(name, "") for name in FIELDS},
                        "status": status, "created": now(), "modified": now()}
                cards.append(card)
            elif action == "update":
                fields = self._clean(payload.get("fields"), require_title=False)
                if "title" in fields and not fields["title"]:
                    raise ValueError("Scene title cannot be empty.")
                # Revalidate when a chapter or draft link changes; otherwise a
                # chapter rename could silently point to the wrong draft.
                next_chapter = fields.get("chapter", card["chapter"])
                next_links = dict(fields)
                if "chapter" in fields and "draft_filename" not in fields:
                    next_links["draft_filename"] = card.get("draft_filename", "")
                self._validate_links(project, book, next_chapter, next_links)
                card.update(fields)
                card["modified"] = now()
            elif action in ("move", "park"):
                status = "parked" if action == "park" else payload.get("status")
                if status not in LANES:
                    raise ValueError("Unknown scene lane.")
                before_id = payload.get("before_id") if action == "move" else None
                if before_id is not None and before_id == card["id"]:
                    raise ValueError("A card cannot move before itself.")
                cards.remove(card)
                card["status"] = status
                if before_id:
                    insert_at = next((i for i, c in enumerate(cards)
                                      if c["id"] == before_id and c["status"] == status), None)
                    if insert_at is None:
                        raise ValueError("Target scene is not in the chosen lane.")
                    cards.insert(insert_at, card)
                else:
                    cards.append(card)
                card["modified"] = now()
            else:
                raise ValueError("Supported scene actions: add, update, move, park.")
            data["modified"] = now()
            if path.exists():
                backup = self.store.backup_file(path, kind="scene_boards")
                if backup is None:
                    raise ValueError("Unable to safeguard existing scene board.")
            jwrite(path, data)
            return {"ok": True, "action": action, "card_id": card["id"],
                    "board": data, "revision": self._revision(path.read_bytes()),
                    "saved": True, "manuscript_unchanged": True,
                    "message": "Scene board updated; no manuscripts or chapter drafts were changed."}
