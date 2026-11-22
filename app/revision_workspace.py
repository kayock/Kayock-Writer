"""Explicit, non-destructive revision review for saved Story Forge chapters.

A selected existing chapter is read from verified Story Forge version history.
The author edits a separate candidate, previews its diff, then explicitly
approves appending that exact candidate as the next canonical draft version.
No model calls, automatic changes, branch merges, or background saves.
The HTTP adapter must serialize preview and accept with ordinary draft saves.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from .storage import contained, slug
from .storyforge import change_metrics, word_count

MAX_TEXT = 80000
MAX_DIFF_LINES = 400
MAX_HISTORY_BYTES = 3_000_000


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_candidate(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_TEXT:
        raise ValueError("Candidate revision must be text of 1–80,000 characters; no text was truncated.")
    # Story Forge's existing _text helper strips outer whitespace. Refuse
    # differences instead of silently saving a different candidate.
    if (not value.strip() or value != value.strip()
            or "\x00" in value or "\r" in value):
        raise ValueError(
            "Remove leading/trailing whitespace, NULs and carriage returns "
            "from the candidate before preview. No characters are silently changed."
        )
    if value.splitlines()[0].lstrip().startswith("#"):
        # StoryForge._draft_body currently treats a leading Markdown heading
        # as generated front matter. Do not accept text that its existing
        # reader would remove on the next load, invalidating source hashes.
        raise ValueError(
            "A leading Markdown heading is not supported by the existing "
            "Story Forge draft reader. Move the heading into the chapter "
            "metadata before saving; nothing was altered."
        )
    return value


class RevisionWorkspace:
    def __init__(self, storyforge, draft_branches):
        self.forge = storyforge
        self.branches = draft_branches

    def _book(self, project_id: Any, book_id: Any):
        if not isinstance(project_id, str) or not isinstance(book_id, str):
            raise ValueError("Choose a saved Story Forge project and book.")
        project, book, root, _ = self.branches._scope(project_id, book_id)
        drafts = root / "Drafts" / slug(book).lower()
        history_file = drafts / "draft_manifest.json"
        if (not contained(history_file, root) or history_file.is_symlink()
                or not history_file.is_file() or history_file.stat().st_size > MAX_HISTORY_BYTES):
            raise ValueError("Saved chapter version history is missing or unsafe.")
        raw = history_file.read_bytes()
        if len(raw) > MAX_HISTORY_BYTES:
            raise ValueError("Saved draft history exceeds the revision size limit.")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Saved draft history is damaged; nothing changed.") from exc
        if (not isinstance(data, dict) or not isinstance(data.get("versions"), list)
                or len(data["versions"]) > 10000):
            raise ValueError("Saved draft history has an unsupported format.")
        return project, book, drafts, raw, data["versions"]

    @staticmethod
    def _verified_entries(history: list):
        records = []
        for entry in history:
            if not isinstance(entry, dict):
                raise ValueError("Draft history contains an invalid version record.")
            name = entry.get("filename")
            chapter = entry.get("chapter")
            digest = entry.get("content_sha256")
            version = entry.get("version")
            if (not isinstance(name, str) or not name.endswith(".md")
                    or Path(name).name != name or "/" in name or "\\" in name
                    or not isinstance(chapter, str) or not chapter.strip() or len(chapter) > 200
                    or type(version) is not int or version < 1
                    or not isinstance(digest, str) or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)):
                raise ValueError("Draft history contains invalid references; nothing changed.")
            records.append(entry)
        return records

    def options(self, project_id: str, book_id: str) -> Dict[str, Any]:
        project, book, _, _, history = self._book(project_id, book_id)
        chapters = {}
        for entry in self._verified_entries(history):
            chapters[entry["chapter"]] = entry
        return {
            "ok": True, "project_id": project, "book_id": book,
            "chapters": [
                {"chapter": entry["chapter"], "version": entry["version"],
                 "filename": entry["filename"], "word_count": entry.get("word_count", 0)}
                for entry in chapters.values()
            ],
            "read_only": True, "source_unchanged": True,
            "message": "Choose an existing saved chapter; only its latest saved version can be revised here.",
        }

    def _state(self, request: Dict[str, Any]):
        if not isinstance(request, dict):
            raise ValueError("Revision request must be a JSON object.")
        chapter = request.get("chapter")
        if not isinstance(chapter, str) or not chapter.strip() or len(chapter) > 200:
            raise ValueError("Choose an existing saved chapter.")
        project, book, drafts, raw_history, history = self._book(
            request.get("project_id"), request.get("book_id")
        )
        matches = [entry for entry in self._verified_entries(history)
                   if entry["chapter"] == chapter]
        if not matches:
            raise ValueError("Selected chapter has no saved canonical draft.")
        entry = matches[-1]
        path = drafts / entry["filename"]
        if (not contained(path, drafts) or path.is_symlink() or not path.is_file()
                or path.stat().st_size > 320000):
            raise ValueError("The latest saved chapter is missing or unsafe.")
        raw = path.read_bytes()
        if len(raw) > 320000:
            raise ValueError("The latest saved chapter is too large to verify.")
        try:
            text = self.forge._draft_body(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Saved chapter is not valid UTF-8.") from exc
        if not text.strip() or _hash(text.encode("utf-8")) != entry["content_sha256"]:
            raise ValueError("Saved chapter differs from its history. No revisions were applied.")
        return {
            "project": project, "book": book, "chapter": chapter,
            "entry": entry, "text": text,
            "history_hash": _hash(raw_history), "source_file_hash": _hash(raw),
        }

    def load(self, request: Dict[str, Any]) -> Dict[str, Any]:
        state = self._state(request)
        return {
            "ok": True, "read_only": True, "source_unchanged": True,
            "project_id": state["project"], "book_id": state["book"],
            "chapter": state["chapter"], "filename": state["entry"]["filename"],
            "version": state["entry"]["version"], "text": state["text"],
            "sha256": state["entry"]["content_sha256"],
            "message": "Verified latest saved chapter loaded for comparison; no file was modified.",
        }

    def _preview_state(self, request: Dict[str, Any]):
        candidate = _safe_candidate(request.get("candidate"))
        state = self._state(request)
        if candidate == state["text"]:
            raise ValueError("The candidate matches the saved chapter; nothing to approve.")
        identity = {
            "schema": "kayock.writer.author_revision.v1",
            "project": state["project"], "book": state["book"], "chapter": state["chapter"],
            "version": state["entry"]["version"],
            "filename": state["entry"]["filename"],
            "source_file_hash": state["source_file_hash"],
            "history_hash": state["history_hash"],
            "candidate_hash": _hash(candidate.encode("utf-8")),
        }
        token = _hash(json.dumps(
            identity, sort_keys=True, ensure_ascii=False,
            separators=(",", ":")
        ).encode("utf-8"))
        return state, candidate, token

    def preview(self, request: Dict[str, Any]) -> Dict[str, Any]:
        state, candidate, token = self._preview_state(request)
        full_diff = list(difflib.unified_diff(
            state["text"].splitlines(), candidate.splitlines(),
            fromfile="current saved chapter", tofile="proposed author revision",
            lineterm=""
        ))
        return {
            "ok": True, "read_only": True,
            "source_unchanged": True, "candidate_saved": False,
            "chapter": state["chapter"], "source_filename": state["entry"]["filename"],
            "current_version": state["entry"]["version"],
            "expected_next_version": state["entry"]["version"] + 1,
            "source_words": word_count(state["text"]),
            "candidate_words": word_count(candidate),
            "diff_metrics": change_metrics(state["text"], candidate),
            "diff_lines": full_diff[:MAX_DIFF_LINES],
            "diff_preview_truncated": len(full_diff) > MAX_DIFF_LINES,
            "confirmation_token": token,
            "message": "Preview only. The full candidate remains intact. "
                       "Author approval is required to save a new version.",
        }

    def accept(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(request, dict) or request.get("approved") is not True:
            raise ValueError("Explicit author approval is required to save a revision.")
        given = request.get("confirmation_token")
        if not isinstance(given, str) or len(given) != 64:
            raise ValueError("Preview the exact proposed revision before approval.")
        state, candidate, current_token = self._preview_state(request)
        if given != current_token:
            raise ValueError("Saved source, project history or proposed text changed since preview. Preview again.")
        result = self.forge.draft_save_action({
            "project_id": state["project"], "book_id": state["book"],
            "chapter": state["chapter"], "content": candidate,
            "model": "author-approved manual revision", "execute": True,
        })
        if not result.get("ok") or not result.get("action_taken"):
            raise ValueError(result.get("message") or "A new draft version could not be saved.")
        return {
            "ok": True, "accepted": True,
            "chapter": state["chapter"], "canonical_version": result["version"],
            "canonical_path": result["path"],
            "source_filename": state["entry"]["filename"],
            "source_version": state["entry"]["version"],
            "original_versions_preserved": True,
            "source_unchanged": True,
            "message": "Author-approved revision saved as a NEW canonical version. "
                       "Earlier draft versions remain available.",
        }
