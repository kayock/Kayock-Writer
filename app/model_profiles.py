"""Opt-in, inert profiles for existing OpenAI-compatible model settings.

Profiles are presets, not active providers. Recording, listing and previewing
never changes a live endpoint or makes model/network requests. API keys are
never stored here; config/environment credentials remain separate.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlsplit

from .storage import Store, jwrite

_FIELDS = ("base_url", "chat_path", "health_path", "health_kind",
           "model", "timeout_seconds")
_PATHS = ("chat_path", "health_path")
_KINDS = frozenset(("auto", "http_status", "openai_models"))
_SCHEMA = "kayock.writer.model_profiles.v1"


def validate_settings(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Model profile settings must be a JSON object.")
    if set(value) - set(_FIELDS):
        raise ValueError("Model profiles contain endpoint metadata only; API keys and other fields cannot be stored.")
    if any(k not in value for k in _FIELDS):
        raise ValueError("Include all six existing model endpoint fields.")
    result = {}
    for field in ("base_url", "model") + _PATHS:
        v = value[field]
        if not isinstance(v, str) or not v.strip() or len(v) > 1024:
            raise ValueError(field + " must be a nonempty string, at most 1024 characters.")
        result[field] = v.strip()
    parts = urlsplit(result["base_url"])
    if (parts.scheme not in ("http", "https") or not parts.hostname
            or parts.username is not None or parts.password is not None
            or parts.query or parts.fragment or any(c.isspace() for c in result["base_url"])):
        raise ValueError("Base URL must be an http(s) endpoint without credentials or query parameters.")
    for name in _PATHS:
        if (not result[name].startswith("/") or result[name].startswith("//")
                or any(c.isspace() for c in result[name])):
            raise ValueError(name + " must start with a single '/' and contain no whitespace.")
    kind = value["health_kind"]
    if kind not in _KINDS:
        raise ValueError("Unknown health check kind.")
    result["health_kind"] = kind
    timeout = value["timeout_seconds"]
    if type(timeout) is not int or not 1 <= timeout <= 604800:
        raise ValueError("Timeout must be a whole number of seconds between 1 and 604800.")
    result["timeout_seconds"] = timeout
    return result


class ModelProfiles:
    """Locally stored named presets, with an explicit read-only preview flow."""

    def __init__(self, store: Store):
        self.store = store
        self._lock = threading.RLock()

    def _path(self) -> Path:
        return self.store.folder("projects") / "ModelProfiles" / "profiles.json"

    def _load(self) -> Dict[str, Any]:
        path = self._path()
        if not path.exists():
            return {"schema": _SCHEMA, "profiles": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("Saved model profiles are damaged; refusing to overwrite.") from exc
        if (not isinstance(data, dict) or data.get("schema") != _SCHEMA
                or not isinstance(data.get("profiles"), list)):
            raise ValueError("Unsupported model profile format; refusing to overwrite.")
        ids, names = set(), set()
        if len(data["profiles"]) > 100:
            raise ValueError("Saved model profile list is out of bounds; refusing to overwrite.")
        for entry in data["profiles"]:
            if not isinstance(entry, dict) or set(entry) != {"id", "name", "settings"}:
                raise ValueError("Saved model profile data is incompatible; refusing to overwrite.")
            pid, name = entry["id"], entry["name"]
            if (not isinstance(pid, str) or len(pid) != 32
                    or any(c not in "0123456789abcdef" for c in pid)
                    or not isinstance(name, str) or not name.strip()
                    or len(name) > 80 or pid in ids or name.casefold() in names):
                raise ValueError("Saved model profile identifiers are invalid; refusing to overwrite.")
            validate_settings(entry["settings"])
            ids.add(pid)
            names.add(name.casefold())
        return data

    def list(self) -> Dict[str, Any]:
        with self._lock:
            data = self._load()
            profiles = [
                {"id": p["id"], "name": p["name"], "settings": dict(p["settings"])}
                for p in data["profiles"]
            ]
            return {
                "ok": True, "profiles": profiles,
                "active_changed": False,
                "credentials_stored": False,
                "message": "Saved presets only; no profile is automatically activated.",
            }

    def save(self, name: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            raise ValueError("A profile name up to 80 characters is required.")
        name = name.strip()
        safe = validate_settings(settings)
        with self._lock:
            data = self._load()
            if len(data["profiles"]) >= 100 and not any(
                    p["name"].casefold() == name.casefold() for p in data["profiles"]):
                raise ValueError("Maximum of 100 saved model presets.")
            existing = next((p for p in data["profiles"]
                             if p["name"].casefold() == name.casefold()), None)
            if existing is not None:
                # Updating a saved preset is not implicit; require explicit ID
                # through a separately authorized edit route in future.
                raise ValueError("That profile name already exists; choose another name.")
            profile = {"id": uuid.uuid4().hex, "name": name, "settings": safe}
            data["profiles"].append(profile)
            jwrite(self._path(), data)
            return {
                "ok": True, "profile": dict(profile),
                "active_changed": False, "credentials_stored": False,
                "message": "Profile saved. Active model settings are unchanged.",
            }

    def delete(self, profile_id: str) -> Dict[str, Any]:
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Select a saved profile.")
        with self._lock:
            data = self._load()
            item = next((p for p in data["profiles"] if p["id"] == profile_id), None)
            if item is None:
                raise ValueError("Profile not found.")
            data["profiles"] = [p for p in data["profiles"] if p["id"] != profile_id]
            path = self._path()
            self.store.backup_file(path, kind="model_profiles")
            jwrite(path, data)
            return {
                "ok": True, "deleted": item["name"],
                "active_changed": False,
                "message": "Saved preset deleted; active model settings unchanged.",
            }
