"""Kayock Writer configuration.

A single JSON config file controls the LAN server and the OpenAI-compatible
model endpoint. Precedence (highest wins):

1. CLI arguments (see kayock_writer.py)
2. Environment variables (KAYOCK_WRITER_*)
3. Config file (default: ./config.json next to kayock_writer.py, or --config)
4. Built-in defaults

Secrets: the model API key may be stored in the config file, but the
KAYOCK_MODEL_API_KEY environment variable is preferred. The key is never
logged or echoed by the app.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {
        "host": "0.0.0.0",          # 0.0.0.0 = reachable from the LAN
        "port": 8765,
        "allow_folder_open": True,  # server-side "open folder" convenience
    },
    "model": {
        # Any OpenAI-compatible chat server works:
        #   llama.cpp llama-server, LM Studio, Ollama (/v1), llamafile,
        #   vLLM, text-generation-webui (openai extension), or a remote API.
        "base_url": "http://127.0.0.1:8080",
        "chat_path": "/v1/chat/completions",
        "health_path": "/health",
        "health_kind": "auto",      # auto | http_status | openai_models
        "model": "local-model",
        # fixed = always use model.model
        # ollama_active = use Ollama /api/ps (never load/unload models)
        "selection_mode": "fixed",
        # Send think:false so reasoning models keep token budget for writing
        "disable_thinking": True,
        "api_key": "",              # prefer KAYOCK_MODEL_API_KEY env var
        "timeout_seconds": 420,
    },
    "paths": {
        # All writing data lives under data_dir. Use an absolute path or a
        # path relative to the config file location.
        "data_dir": "./KayockWriterData",
    },
    "writing": {
        "default_author": "Eric Z. Fox",
        "require_approval_phrase": True,  # Story Forge gate actions
        "archive_limit": 500,
        "editorial_max_tokens": 4000,  # user-configurable, no model changes
    },
    "integrations": {
        "craft_suite_url": "",  # optional browser handoff; no API assumed
    },
}


class Config:
    """Loaded configuration with deep-merged overrides."""

    def __init__(self, data: Dict[str, Any], path: Path | None = None):
        self.data = data
        self.path = path

    # -- generic accessors -------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    # -- resolved values ---------------------------------------------------
    @property
    def host(self) -> str:
        return str(self.get("server.host", "0.0.0.0"))

    @property
    def port(self) -> int:
        return int(self.get("server.port", 8765))

    @property
    def allow_folder_open(self) -> bool:
        return bool(self.get("server.allow_folder_open", True))

    @property
    def require_approval_phrase(self) -> bool:
        return bool(self.get("writing.require_approval_phrase", True))

    @property
    def default_author(self) -> str:
        return str(self.get("writing.default_author", "Eric Z. Fox"))

    @property
    def archive_limit(self) -> int:
        try:
            return max(10, int(self.get("writing.archive_limit", 500)))
        except Exception:
            return 500

    def model_settings(self) -> Dict[str, Any]:
        return dict(self.get("model") or {})

    def api_key(self) -> str:
        env_key = os.environ.get("KAYOCK_MODEL_API_KEY", "")
        return env_key or str(self.get("model.api_key", "") or "")

    def public_view(self) -> Dict[str, Any]:
        """Config safe to send to the browser (API key masked)."""
        key_set = bool(self.api_key())
        view = json.loads(json.dumps(self.data))  # deep copy
        view.setdefault("model", {})["api_key_set"] = key_set
        view["model"]["api_key"] = ""  # never send the secret
        view["_resolved"] = {
            "data_dir": str(self.data_dir()),
            "base_url": self.get("model.base_url", ""),
        }
        return view

    # -- paths ---------------------------------------------------------------
    def data_dir(self) -> Path:
        raw = os.environ.get(
            "KAYOCK_WRITER_DATA",
            str(self.get("paths.data_dir", "./KayockWriterData")),
        )
        path = Path(raw).expanduser()
        if not path.is_absolute() and self.path is not None:
            path = (self.path.parent / path).resolve()
        else:
            path = path.resolve()
        return path


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _env_overrides() -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if os.environ.get("KAYOCK_WRITER_HOST"):
        data.setdefault("server", {})["host"] = os.environ["KAYOCK_WRITER_HOST"]
    if os.environ.get("KAYOCK_WRITER_PORT"):
        data.setdefault("server", {})["port"] = int(os.environ["KAYOCK_WRITER_PORT"])
    if os.environ.get("KAYOCK_MODEL_BASE_URL"):
        data.setdefault("model", {})["base_url"] = os.environ["KAYOCK_MODEL_BASE_URL"]
    if os.environ.get("KAYOCK_MODEL_NAME"):
        data.setdefault("model", {})["model"] = os.environ["KAYOCK_MODEL_NAME"]
    if os.environ.get("KAYOCK_MODEL_API_KEY"):
        data.setdefault("model", {})["api_key_env"] = True
    return data


def apply_cli_overrides(cfg: Config, args: Dict[str, Any]) -> Config:
    """Apply parsed CLI argument dict (only provided keys are applied)."""
    if args.get("host"):
        cfg.set("server.host", args["host"])
    if args.get("port"):
        cfg.set("server.port", int(args["port"]))
    if args.get("data_dir"):
        cfg.set("paths.data_dir", args["data_dir"])
    if args.get("base_url"):
        cfg.set("model.base_url", args["base_url"])
    if args.get("model"):
        cfg.set("model.model", args["model"])
    return cfg


def load_config(config_path: str | Path | None = None) -> Config:
    path: Path | None = None
    file_data: Dict[str, Any] = {}
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    else:
        candidates.append(Path(__file__).resolve().parent.parent / "config.json")
    for candidate in candidates:
        if candidate.is_file():
            path = candidate
            try:
                file_data = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception as exc:
                raise ValueError(f"Could not parse config file {candidate}: {exc}")
            break
    merged = _deep_merge(DEFAULT_CONFIG, file_data)
    merged = _deep_merge(merged, _env_overrides())
    return Config(merged, path)


def save_config(cfg: Config) -> None:
    """Persist the current config to its file (creating one if needed)."""
    path = cfg.path or Path(__file__).resolve().parent.parent / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(json.dumps(cfg.data))
    # Do not persist a secret that only came from the environment.
    model = payload.get("model") or {}
    if os.environ.get("KAYOCK_MODEL_API_KEY"):
        model.pop("api_key", None)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    cfg.path = path
