"""OpenAI-compatible model provider for Kayock Writer.

Replaces FOXAI's hard-wired `_poetry_chat` (CHAT_HEALTH/CHAT_API against a
local llama-server on 127.0.0.1:8080) with a configurable client. Any server
speaking the OpenAI chat-completions protocol works:

    llama.cpp llama-server, LM Studio, Ollama (/v1), llamafile, vLLM,
    text-generation-webui, or a hosted API.

Message/response semantics match FOXAI: a system+user pair in, the first
choice's text content out, `{"ok": False, "message": ...}` on any failure so
caller workflows never raise.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .config import Config


class Provider:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    # -- settings -----------------------------------------------------------
    def settings(self) -> Dict[str, Any]:
        return self.cfg.model_settings()

    def base_url(self) -> str:
        return str(self.cfg.get("model.base_url", "http://127.0.0.1:8080")).rstrip("/")

    def model_name(self) -> str:
        return str(self.cfg.get("model.model", "local-model"))

    def timeout(self) -> int:
        try:
            return max(5, int(self.cfg.get("model.timeout_seconds", 420)))
        except Exception:
            return 420

    def display_model(self) -> str:
        return self.model_name() or "active model"

    # -- endpoints ------------------------------------------------------------
    def chat_url(self) -> str:
        path = str(self.cfg.get("model.chat_path", "/v1/chat/completions"))
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url() + path

    def health_url(self) -> str:
        path = str(self.cfg.get("model.health_path", "/health"))
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url() + path

    # -- plumbing ---------------------------------------------------------------
    def _request(self, url: str, payload: Dict[str, Any] | None, timeout: float) -> tuple[bool, Any, str]:
        headers = {"Content-Type": "application/json"}
        api_key = self.cfg.api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            return True, body, ""
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                pass
            return False, None, f"HTTP {exc.code}: {detail or exc.reason}"
        except Exception as exc:
            return False, None, f"{type(exc).__name__}: {exc}"

    # -- public API ---------------------------------------------------------------
    def health(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Check the model endpoint. health_kind:
        - http_status: any 2xx on health_path means online
        - openai_models: GET /v1/models must return JSON
        - auto: try openai_models, fall back to http_status
        """
        kind = str(self.cfg.get("model.health_kind", "auto")).casefold()
        checked = []
        if kind in ("auto", "openai_models"):
            base = self.base_url()
            ok, body, err = self._request(base + "/v1/models", None, timeout)
            checked.append({"endpoint": base + "/v1/models", "ok": ok, "error": err})
            if ok:
                try:
                    json.loads(body)
                    return {"ok": True, "online": True, "model": self.display_model(),
                            "checked": checked, "via": "openai_models"}
                except Exception:
                    checked[-1]["error"] = "response was not JSON"
        if kind in ("auto", "http_status"):
            ok, _body, err = self._request(self.health_url(), None, timeout)
            checked.append({"endpoint": self.health_url(), "ok": ok, "error": err})
            if ok:
                return {"ok": True, "online": True, "model": self.display_model(),
                        "checked": checked, "via": "http_status"}
        return {"ok": False, "online": False, "model": self.display_model(),
                "checked": checked,
                "message": "The configured model endpoint is not responding. "
                           "Check Settings → Model endpoint."}

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 900,
             temperature: float = 0.82) -> Dict[str, Any]:
        """One chat completion. Returns {'ok': bool, 'text'/'message', ...}."""
        payload = {
            "model": self.model_name(),
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "stream": False,
        }
        ok, body, err = self._request(self.chat_url(), payload, self.timeout())
        if not ok:
            return {"ok": False,
                    "message": f"Kayock Writer could not reach the model endpoint ({self.base_url()}): {err}"}
        try:
            data = json.loads(body)
            content = str(data["choices"][0]["message"]["content"]).strip()
        except Exception as exc:
            return {"ok": False,
                    "message": f"The model endpoint returned an unreadable response: {type(exc).__name__}"}
        if not content:
            return {"ok": False, "message": "The model returned an empty response."}
        return {"ok": True, "text": content, "model_name": self.display_model()}
