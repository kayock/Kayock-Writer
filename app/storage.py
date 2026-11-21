"""Kayock Writer storage helpers.

App-owned storage replaces FOXAI's globals (ROOT/FOLDERS/jread/jwrite/slug)
with safe, path-checked operations rooted at a configurable data directory.

Layout (under data_dir):

    Projects/KayockWriter/Poetry/Drafts          poem drafts (*.md front-matter)
    Projects/KayockWriter/ShortStories/Drafts    short-story drafts
    Projects/KayockWriter/Poetry/Recordings      voice-recording folders
    Projects/KayockWriter/Poetry/Legacy          legacy manifest
    Projects/KayockWriter/Weaver/Outputs         woven works
    Projects/KayockWriter/<StoryProject>/        Story Forge projects
    NovelForge/                                  Novel Forge universes (+ Markdown/, Exports/)
    Reports/KayockWriter/...                     action receipts
    Backups/KayockWriter/...                     pre-overwrite backups
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9 ._\-]")


def slug(name: str) -> str:
    """FOXAI-compatible slug: keep alnum/space/dot/dash/underscore."""
    return (
        _SAFE_NAME_RE.sub("", str(name or ""))
        .strip()
        .replace(" ", "_")[:80]
        or "New_Project"
    )


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def jread(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def jwrite(path: Path, data: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def contained(child: Path, parent: Path) -> bool:
    """True when child resolves inside parent (path traversal guard)."""
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except Exception:
        return False


def safe_child(base: Path, name: str, must_exist: bool = False) -> Path | None:
    """Resolve name under base, rejecting traversal and absolute paths."""
    candidate = (Path(base) / Path(str(name or "")).name).resolve()
    if not contained(candidate, base):
        return None
    if must_exist and not candidate.is_file():
        return None
    return candidate


class Store:
    """All folders Kayock Writer owns, rooted at a configurable data dir."""

    def __init__(self, data_dir: Path):
        self.root = Path(data_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        kw = self.root / "Projects" / "KayockWriter"
        self.folders = {
            "root": self.root,
            "projects": kw,
            "poetry_drafts": kw / "Poetry" / "Drafts",
            "poetry_recordings": kw / "Poetry" / "Recordings",
            "poetry_legacy": kw / "Poetry" / "Legacy",
            "short_story_drafts": kw / "ShortStories" / "Drafts",
            "weaver_outputs": kw / "Weaver" / "Outputs",
            "novel_forge": self.root / "NovelForge",
            "novel_exports": self.root / "NovelForge" / "Exports",
            "reports": self.root / "Reports" / "KayockWriter",
            "backups": self.root / "Backups" / "KayockWriter",
            "chapter_edit_backups": self.root / "Backups" / "KayockWriter" / "ChapterEdits",
        }

    def folder(self, key: str) -> Path:
        if key not in self.folders:
            raise KeyError(f"Unknown folder key: {key}")
        path = self.folders[key]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def report_dir(self, tool: str) -> Path:
        path = self.folders["reports"] / slug(tool)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_report(self, tool: str, payload: dict) -> Path:
        directory = self.report_dir(tool)
        path = directory / f"{stamp()}_{slug(tool)}.json"
        return jwrite(path, payload)

    def backup_file(self, path: Path, kind: str = "edits") -> Path | None:
        """Copy an existing file into the backups tree before overwrite."""
        src = Path(path)
        if not src.is_file():
            return None
        target_dir = (
            self.folders["chapter_edit_backups"]
            if kind == "edits"
            else self.folders["backups"] / slug(kind)
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{src.stem}_{stamp()}{src.suffix}"
        target.write_bytes(src.read_bytes())
        return target
