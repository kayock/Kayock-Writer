"""Explicit, version-checked Novel Forge recovery from app-owned JSON backups.

A snapshot is never restored merely by listing or previewing it. The restore
operation needs a preview fingerprint and preserves the current universe.
No automatic migration, merging, model inference, or remote storage.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Dict

from .novelforge import NovelForge, render_universe_markdown
from .storage import Store, atomic_write_text, contained

_REQUIRED_LISTS = ("characters", "locations", "artifacts", "timeline",
                   "mysteries", "scenes")


class UniverseRecovery:
    def __init__(self, store: Store, forge: NovelForge):
        self.store, self.forge = store, forge
        self._lock = threading.RLock()

    def _target(self, name: str) -> Path:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("A saved universe must be selected.")
        target = self.forge.novel_path(name)
        if target is None or not target.is_file() or target.is_symlink():
            raise ValueError("Universe is not available for recovery.")
        return target

    def _backup_dir(self) -> Path:
        return self.store.folder("backups") / "universes"

    def _backup_path(self, target: Path, backup_id: str) -> Path:
        if (not isinstance(backup_id, str) or not backup_id
                or Path(backup_id).name != backup_id
                or "\\" in backup_id or "/" in backup_id
                or not backup_id.startswith(target.stem + "_")
                or not backup_id.endswith(".json")):
            raise ValueError("Invalid backup identifier.")
        base = self._backup_dir()
        candidate = base / backup_id
        if candidate.is_symlink() or not candidate.is_file() or not contained(candidate, base):
            raise ValueError("Backup not found.")
        return candidate

    def _snapshot(self, backup: Path, target: Path):
        if backup.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Backup exceeds recovery preview limit; no changes made.")
        raw = backup.read_bytes()
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Backup is not valid UTF-8 JSON; no changes made.") from exc
        if not isinstance(obj, dict):
            raise ValueError("Unsupported backup format.")
        identifier = str(obj.get("file_name") or obj.get("universe") or "")
        if not identifier or self.forge.novel_path(identifier) != target:
            raise ValueError("Backup belongs to another universe; no changes made.")
        for key in _REQUIRED_LISTS:
            if not isinstance(obj.get(key), list) or any(
                    not isinstance(x, str) for x in obj[key]):
                raise ValueError("Backup does not contain compatible universe lists.")
        for key in ("universe", "premise", "notes", "modified"):
            if not isinstance(obj.get(key), str):
                raise ValueError("Backup does not contain compatible universe fields.")
        return obj, raw

    @staticmethod
    def _hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _state(self, target: Path, backup: Path):
        current = target.read_bytes()
        mirror = self.forge.novel_md_path(target.stem)
        md_bytes = mirror.read_bytes() if mirror.is_file() and not mirror.is_symlink() else b""
        snapshot, original_bytes = self._snapshot(backup, target)
        try:
            existing = json.loads(current.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Current universe JSON is damaged; use manual recovery.") from exc
        if not isinstance(existing, dict):
            raise ValueError("Current universe is not a JSON object.")
        token = self._hash(
            b"KayockRecoveryV1\0" + target.stem.encode("utf-8") + b"\0"
            + backup.name.encode("utf-8") + b"\0"
            + self._hash(current).encode("ascii") + b"\0"
            + self._hash(md_bytes).encode("ascii") + b"\0"
            + self._hash(original_bytes).encode("ascii")
        )
        return snapshot, original_bytes, existing, current, md_bytes, token

    def list_backups(self, name: str) -> Dict[str, Any]:
        with self._lock:
            target = self._target(name)
            base = self._backup_dir()
            results = []
            if base.is_dir():
                for path in base.glob(target.stem + "_*.json"):
                    try:
                        self._backup_path(target, path.name)
                        record, raw = self._snapshot(path, target)
                    except (OSError, ValueError):
                        continue  # Ignore corrupt and foreign backups, never delete them.
                    results.append({
                        "id": path.name,
                        "modified": str(record["modified"]),
                        "size_bytes": len(raw),
                        "recorded_premise": str(record.get("premise", ""))[:150],
                        "sha256": self._hash(raw),
                    })
            results.sort(key=lambda row: row["id"], reverse=True)
            return {"ok": True, "universe": target.stem, "backups": results,
                    "read_only": True}

    def preview(self, name: str, backup_id: str) -> Dict[str, Any]:
        with self._lock:
            target = self._target(name)
            backup = self._backup_path(target, backup_id)
            old, _, current, _, _, token = self._state(target, backup)
            return {
                "ok": True, "universe": target.stem, "backup_id": backup.name,
                "confirmation_token": token,
                "snapshot": {
                    "title": old["universe"], "modified": old["modified"],
                    "premise": old["premise"][:300],
                    "counts": {k: len(old[k]) for k in _REQUIRED_LISTS},
                },
                "current": {
                    "title": current.get("universe", target.stem),
                    "modified": current.get("modified", ""),
                    "premise": str(current.get("premise", ""))[:300],
                    "counts": {k: len(current.get(k, [])) if isinstance(current.get(k), list) else 0
                               for k in _REQUIRED_LISTS},
                },
                "read_only": True,
                "message": "Preview only. Confirm restore to replace the current JSON and its Markdown mirror.",
            }

    def restore(self, name: str, backup_id: str, confirmation_token: str) -> Dict[str, Any]:
        """A user-initiated restore, guarded against changes since preview."""
        with self._lock:
            target = self._target(name)
            backup = self._backup_path(target, backup_id)
            if not isinstance(confirmation_token, str) or len(confirmation_token) != 64:
                raise ValueError("Preview the backup again before restoring.")
            snapshot, original, _, current, _, token = self._state(target, backup)
            if token != confirmation_token:
                raise ValueError("Universe or backup changed since preview. Preview again; nothing was restored.")
            mirror = self.forge.novel_md_path(target.stem)
            if mirror.is_symlink():
                raise ValueError("Unsafe Markdown mirror path; no changes made.")
            had_mirror = mirror.is_file()
            previous_mirror = mirror.read_bytes() if had_mirror else b""
            markdown = render_universe_markdown(snapshot)
            # Critical: backup the current author-approved state before replacement.
            safe_json = self.store.backup_file(target, kind="universes")
            safe_md = self.store.backup_file(mirror, kind="universe_markdown") if had_mirror else None
            if safe_json is None:
                raise ValueError("Could not safeguard current universe; no changes made.")
            # Re-check after the copy; stale previews never overwrite recent edits.
            _, _, _, latest, _, latest_token = self._state(target, backup)
            if latest_token != token or latest != current:
                raise ValueError("Universe changed while preparing restore. Nothing was replaced.")
            try:
                atomic_write_text(target, original.decode("utf-8"))
                atomic_write_text(mirror, markdown)
            except Exception:
                # Best-effort rollback from the captured original.
                atomic_write_text(target, current.decode("utf-8"))
                if had_mirror:
                    atomic_write_text(mirror, previous_mirror.decode("utf-8"))
                elif mirror.exists():
                    mirror.unlink()
                raise
            return {
                "ok": True, "restored": True, "universe": target.stem,
                "backup_id": backup.name, "saved_current_backup": safe_json.name,
                "saved_current_markdown_backup": safe_md.name if safe_md else None,
                "message": "Restored the selected universe snapshot. A fresh backup of the previous version was retained.",
            }
