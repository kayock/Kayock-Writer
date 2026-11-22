"""Non-destructive branches of saved Story Forge chapter draft versions.

Each branch is a separate, immutable sequence of alternative drafts under the
project's Branches folder. Creating or extending one never mutates the source
draft, its history, a manuscript or an approved chapter.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict

from .storage import Store, atomic_write_text, contained, jwrite, now, slug

SCHEMA = "kayock.writer.draft_branch.v1"
_ID = re.compile(r"^[a-f0-9]{32}$")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class DraftBranches:
    def __init__(self, store: Store, storyforge):
        self.store, self.storyforge = store, storyforge
        self._lock = threading.RLock()

    def _scope(self, project_id: str, book_id: str):
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("Select a saved Story Forge project.")
        if not isinstance(book_id, str) or not book_id.strip():
            raise ValueError("Select a book.")
        manifest = self.storyforge.load_manifest(project_id)
        if not isinstance(manifest, dict) or not manifest.get("project_id"):
            raise ValueError("Story Forge project manifest not found.")
        project = str(manifest["project_id"])
        if not any(isinstance(book, dict) and book.get("id") == book_id
                   for book in manifest.get("books") or []):
            raise ValueError("Book does not belong to this Story Forge project.")
        root = self.storyforge.project_root(project)
        if root is None or not root.is_dir():
            raise ValueError("Story Forge project folder is missing.")
        base = root / "Branches" / slug(book_id)
        if not contained(base, root) or base.is_symlink():
            raise ValueError("Unsafe branch directory.")
        return project, book_id, root, base

    def _branch_path(self, base: Path, branch_id: str) -> Path:
        if not isinstance(branch_id, str) or not _ID.fullmatch(branch_id):
            raise ValueError("Invalid branch ID.")
        path = base / branch_id
        if not contained(path, base) or path.is_symlink():
            raise ValueError("Unsafe branch path.")
        return path

    def _load(self, base: Path, branch_id: str):
        root = self._branch_path(base, branch_id)
        path = root / "branch.json"
        if not path.is_file() or path.is_symlink():
            raise ValueError("Saved branch not found.")
        try:
            raw = path.read_bytes()
            data = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("Saved branch is damaged; refusing to overwrite.") from exc
        if (not isinstance(data, dict) or data.get("schema") != SCHEMA
                or data.get("id") != branch_id
                or not isinstance(data.get("versions"), list)
                or not 1 <= len(data["versions"]) <= 1000):
            raise ValueError("Unsupported branch manifest; refusing to overwrite.")
        seen = set()
        for version in data["versions"]:
            if (not isinstance(version, dict)
                    or not isinstance(version.get("file"), str)
                    or version["file"] in seen
                    or Path(version["file"]).name != version["file"]
                    or not version["file"].endswith(".md")
                    or not isinstance(version.get("sha256"), str)
                    or len(version["sha256"]) != 64):
                raise ValueError("Saved branch versions are damaged.")
            seen.add(version["file"])
        return data, _digest(raw), root

    def _read_version(self, root: Path, item: Dict[str, Any]) -> str:
        filename = item["file"]
        file = root / filename
        if (file.is_symlink() or not file.is_file() or not contained(file, root)
                or file.stat().st_size > 320000):
            raise ValueError("Draft branch version missing or unsafe; no changes made.")
        try:
            content = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError("Draft branch text unreadable.") from exc
        if _digest(content.encode("utf-8")) != item["sha256"]:
            raise ValueError("Draft branch version changed outside Writer; no changes made.")
        return content

    def _source(self, project: str, book: str, root: Path, filename: str):
        if (not isinstance(filename, str) or not filename
                or Path(filename).name != filename or "/" in filename
                or "\\" in filename):
            raise ValueError("Select a listed saved chapter draft version.")
        manifest = self.storyforge._load_draft_manifest(project, book)
        entries = manifest.get("versions") or []
        source = next((x for x in entries if isinstance(x, dict)
                       and x.get("filename") == filename), None)
        if source is None:
            raise ValueError("Source draft is not listed in its version history.")
        drafts = root / "Drafts" / slug(book).lower()
        path = drafts / filename
        if (not contained(path, drafts) or path.is_symlink()
                or not path.is_file() or path.stat().st_size > 320000):
            raise ValueError("Saved source draft missing or unsafe.")
        try:
            text = self.storyforge._draft_body(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            raise ValueError("Saved source draft cannot be read.") from exc
        if not text.strip() or _digest(text.encode("utf-8")) != source.get("content_sha256"):
            raise ValueError("Saved source draft differs from version history; no branch created.")
        return source, text

    def verify_source(self, project_id: str, book_id: str,
                      filename: str, chapter: str = "") -> Dict[str, Any]:
        """Verify a source is in that book's saved history and matches its hash."""
        with self._lock:
            project, book, root, _ = self._scope(project_id, book_id)
            entry, content = self._source(project, book, root, filename)
            if chapter and str(entry.get("chapter") or "") != chapter:
                raise ValueError("Draft belongs to a different chapter than the card.")
            return {
                "ok": True, "filename": filename,
                "chapter": str(entry.get("chapter") or ""),
                "version": entry.get("version"),
                "sha256": _digest(content.encode("utf-8")),
                "read_only": True,
            }

    def list(self, project_id: str, book_id: str, chapter: str = "") -> Dict[str, Any]:
        with self._lock:
            project, book, _, base = self._scope(project_id, book_id)
            found, damaged = [], 0
            if base.is_dir():
                for folder in sorted(base.iterdir()):
                    if not folder.is_dir() or folder.is_symlink():
                        continue
                    try:
                        manifest, revision, _ = self._load(base, folder.name)
                        if chapter and manifest.get("chapter") != chapter:
                            continue
                        found.append({
                            "id": manifest["id"], "name": manifest["name"],
                            "chapter": manifest["chapter"],
                            "source_filename": manifest["source_filename"],
                            "versions": len(manifest["versions"]),
                            "created": manifest.get("created", ""),
                            "revision": revision,
                        })
                    except ValueError:
                        damaged += 1
            return {"ok": True, "project_id": project, "book_id": book,
                    "branches": found, "damaged_branches": damaged,
                    "read_only": True}

    def create(self, project_id: str, book_id: str, filename: str,
               branch_name: str) -> Dict[str, Any]:
        if (not isinstance(branch_name, str) or not branch_name.strip()
                or len(branch_name.strip()) > 100):
            raise ValueError("Give the alternative a branch name up to 100 characters.")
        with self._lock:
            project, book, root, base = self._scope(project_id, book_id)
            source, text = self._source(project, book, root, filename)
            branch_id = uuid.uuid4().hex
            folder = self._branch_path(base, branch_id)
            folder.mkdir(parents=True, exist_ok=False)
            raw_name = "v001_" + uuid.uuid4().hex[:12] + ".md"
            atomic_write_text(folder / raw_name, text)
            manifest = {
                "schema": SCHEMA, "id": branch_id,
                "project_id": project, "book_id": book,
                "chapter": source.get("chapter", ""),
                "name": branch_name.strip(),
                "source_filename": filename,
                "source_sha256": source["content_sha256"],
                "created": now(),
                "versions": [{
                    "version": 1, "file": raw_name, "created": now(),
                    "sha256": _digest(text.encode("utf-8")),
                    "word_count": len(text.split()),
                }],
            }
            jwrite(folder / "branch.json", manifest)
            return {"ok": True, "branch_id": branch_id,
                    "version": 1, "content": text,
                    "message": "Alternative branch created. Original chapter draft and its history unchanged."}

    def read(self, project_id: str, book_id: str, branch_id: str) -> Dict[str, Any]:
        with self._lock:
            project, book, _, base = self._scope(project_id, book_id)
            manifest, rev, folder = self._load(base, branch_id)
            if manifest.get("project_id") != project or manifest.get("book_id") != book:
                raise ValueError("Branch belongs to another project or book.")
            content = self._read_version(folder, manifest["versions"][-1])
            return {"ok": True, "manifest": manifest, "revision": rev,
                    "content": content, "read_only": True,
                    "canonical_unchanged": True}

    def append(self, project_id: str, book_id: str, branch_id: str,
               content: str, expected_revision: str) -> Dict[str, Any]:
        if not isinstance(content, str) or not content.strip() or len(content) > 80000:
            raise ValueError("Alternative draft must be 1–80,000 characters.")
        with self._lock:
            project, book, _, base = self._scope(project_id, book_id)
            manifest, rev, folder = self._load(base, branch_id)
            if manifest.get("project_id") != project or manifest.get("book_id") != book:
                raise ValueError("Branch belongs to another project or book.")
            if not isinstance(expected_revision, str) or expected_revision != rev:
                raise ValueError("Branch changed since loading. Refresh before saving; no changes made.")
            previous = self._read_version(folder, manifest["versions"][-1])
            if previous == content:
                raise ValueError("Alternative text is unchanged; nothing to save.")
            if len(manifest["versions"]) >= 1000:
                raise ValueError("Branch reached its version limit.")
            name = "v" + str(len(manifest["versions"]) + 1).zfill(3) + "_" + uuid.uuid4().hex[:12] + ".md"
            atomic_write_text(folder / name, content)
            manifest["versions"].append({
                "version": len(manifest["versions"]) + 1,
                "file": name, "sha256": _digest(content.encode("utf-8")),
                "word_count": len(content.split()), "created": now(),
            })
            original = folder / "branch.json"
            backup = self.store.backup_file(original, kind="draft_branches")
            if backup is None:
                raise ValueError("Cannot back up branch version history; no manifest changed.")
            jwrite(original, manifest)
            return {"ok": True, "version": len(manifest["versions"]),
                    "revision": _digest(original.read_bytes()),
                    "canonical_unchanged": True,
                    "message": "Alternative version saved. Main draft and prose manuscripts unchanged."}

    def compare_source(self, project_id: str, book_id: str, branch_id: str) -> Dict[str, Any]:
        with self._lock:
            project, book, root, base = self._scope(project_id, book_id)
            manifest, _, folder = self._load(base, branch_id)
            if manifest.get("project_id") != project or manifest.get("book_id") != book:
                raise ValueError("Branch belongs to another project or book.")
            _, source_text = self._source(project, book, root, manifest["source_filename"])
            latest = self._read_version(folder, manifest["versions"][-1])
            diff = list(difflib.unified_diff(
                source_text.splitlines(), latest.splitlines(),
                fromfile="original saved draft", tofile="alternative latest",
                lineterm=""))
            return {"ok": True, "read_only": True,
                    "source_words": len(source_text.split()),
                    "branch_words": len(latest.split()),
                    "different": source_text != latest,
                    "diff_preview": diff[:400], "truncated": len(diff) > 400,
                    "canonical_unchanged": True}
