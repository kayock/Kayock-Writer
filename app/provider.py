"""OpenAI-compatible model provider for Kayock Writer.

Replaces FOXAI's hard-wired `_poetry_chat` (CHAT_HEALTH/CHAT_API against a
local llama-server on 127.0.0.1:8080) with a configurable client. Any server
speaking the OpenAI chat-completions protocol works:

    llama.cpp llama-server, LM Studio, Ollama (/v1), llamafile, vLLM,
    text-generation-webui, or a hosted API.

Message/response semantics match FOXAI: a system+user pair in, the first
choice's text content out, `{"ok": False, "message": ...}` on any failure so
caller workflows never raise.

When ``model.selection_mode`` is ``ollama_active``, the provider reads
Ollama's ``/api/ps`` before each generation and uses the model currently
loaded in memory. It never starts, stops, unloads, or pulls models.
"""
from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List

from .config import Config

    
class Cancellation:
    """Cross-request cancellation signal that closes the active HTTP stream."""

    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._response = None

    def cancelled(self) -> bool:
        return self._event.is_set()

    def bind(self, response) -> None:
        with self._lock:
            if self._event.is_set():
                response.close()
            else:
                self._response = response

    def release(self, response) -> None:
        with self._lock:
            if self._response is response:
                self._response = None

    def cancel(self) -> None:
        self._event.set()
        with self._lock:
            response = self._response
        if response is None:
            return
        # Shutdown wakes the blocked read without racing HTTPResponse.close()
        # against readline(). The reader thread owns final response.close().
        try:
            sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
            if sock is not None:
                sock.shutdown(socket.SHUT_RDWR)
        except (OSError, ValueError, AttributeError):
            pass


class Provider:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    # -- settings -----------------------------------------------------------
    def settings(self) -> Dict[str, Any]:
        return self.cfg.model_settings()

    def base_url(self) -> str:
        return str(self.cfg.get("model.base_url", "http://127.0.0.1:8080")).rstrip("/")

    def selection_mode(self) -> str:
        mode = str(self.cfg.get("model.selection_mode", "fixed") or "fixed").casefold()
        return mode if mode in ("fixed", "ollama_active") else "fixed"

    def preferred_model(self) -> str:
        return str(self.cfg.get("model.model", "") or "").strip()

    def model_name(self) -> str:
        """Configured/preferred name (not necessarily the live active model)."""
        return self.preferred_model() or "local-model"

    def disable_thinking(self) -> bool:
        """Prefer writing content over chain-of-thought token spend."""
        raw = self.cfg.get("model.disable_thinking", True)
        if isinstance(raw, str):
            return raw.strip().casefold() not in ("0", "false", "no", "off")
        return bool(raw)

    def timeout(self) -> int:
        try:
            return max(5, int(self.cfg.get("model.timeout_seconds", 420)))
        except Exception:
            return 420

    def display_model(self) -> str:
        resolved = self.resolve_model(timeout=2.0)
        if resolved.get("ok") and resolved.get("model"):
            return str(resolved["model"])
        return self.preferred_model() or "no active model"

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

    def ollama_ps_url(self) -> str:
        return self.base_url() + "/api/ps"

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

    # -- active Ollama model selection ----------------------------------------
    def list_loaded_models(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Read-only probe of Ollama ``/api/ps``. Never loads or unloads models."""
        ok, body, err = self._request(self.ollama_ps_url(), None, timeout)
        if not ok:
            return {
                "ok": False,
                "models": [],
                "message": f"Could not query Ollama loaded models at {self.ollama_ps_url()}: {err}",
            }
        try:
            data = json.loads(body)
        except Exception:
            return {
                "ok": False,
                "models": [],
                "message": "Ollama /api/ps returned unreadable JSON.",
            }
        names: List[str] = []
        for item in data.get("models") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("model") or item.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        return {"ok": True, "models": names, "raw_count": len(data.get("models") or [])}

    def resolve_model(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Pick the model to use for the next request.

        ``ollama_active``:
          - exactly one loaded → use it
          - multiple loaded → use Settings preferred model if still loaded
          - none loaded → clear error (do not auto-load)
        ``fixed``: use ``model.model`` as before.
        """
        mode = self.selection_mode()
        preferred = self.preferred_model()
        if mode != "ollama_active":
            model = preferred or "local-model"
            return {
                "ok": True,
                "model": model,
                "selection_mode": mode,
                "preferred_model": preferred,
                "loaded_models": [],
                "reason": "fixed",
            }

        loaded = self.list_loaded_models(timeout=timeout)
        if not loaded.get("ok"):
            return {
                "ok": False,
                "model": "",
                "selection_mode": mode,
                "preferred_model": preferred,
                "loaded_models": [],
                "message": loaded.get("message")
                or "Could not determine which Ollama model is active.",
            }

        names = list(loaded.get("models") or [])
        if not names:
            return {
                "ok": False,
                "model": "",
                "selection_mode": mode,
                "preferred_model": preferred,
                "loaded_models": [],
                "message": (
                    f"No model is currently loaded at {self.base_url()}. "
                    "Load a model in Ollama first — Kayock Writer will not "
                    "start or pull models."
                ),
            }
        if len(names) == 1:
            return {
                "ok": True,
                "model": names[0],
                "selection_mode": mode,
                "preferred_model": preferred,
                "loaded_models": names,
                "reason": "single_active",
            }
        if preferred and preferred in names:
            return {
                "ok": True,
                "model": preferred,
                "selection_mode": mode,
                "preferred_model": preferred,
                "loaded_models": names,
                "reason": "preferred_among_active",
            }
        return {
            "ok": False,
            "model": "",
            "selection_mode": mode,
            "preferred_model": preferred,
            "loaded_models": names,
            "message": (
                "Multiple models are loaded in Ollama: "
                + ", ".join(names)
                + ". Choose one in Settings → Model name (preferred model) "
                "while it remains loaded. Kayock Writer will not switch or "
                "unload models automatically."
            ),
        }

    def active_model_status(self, timeout: float = 3.0) -> Dict[str, Any]:
        resolved = self.resolve_model(timeout=timeout)
        return {
            "selection_mode": self.selection_mode(),
            "preferred_model": self.preferred_model(),
            "active_model": resolved.get("model") or "",
            "loaded_models": resolved.get("loaded_models") or [],
            "ok": bool(resolved.get("ok")),
            "reason": resolved.get("reason", ""),
            "message": resolved.get("message", ""),
        }

    # -- public API ---------------------------------------------------------------
    def health(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Check the model endpoint. health_kind:
        - http_status: any 2xx on health_path means online
        - openai_models: GET /v1/models must return JSON
        - auto: try openai_models, fall back to http_status
        """
        kind = str(self.cfg.get("model.health_kind", "auto")).casefold()
        checked = []
        endpoint_online = False
        via = ""
        if kind in ("auto", "openai_models"):
            base = self.base_url()
            ok, body, err = self._request(base + "/v1/models", None, timeout)
            checked.append({"endpoint": base + "/v1/models", "ok": ok, "error": err})
            if ok:
                try:
                    json.loads(body)
                    endpoint_online = True
                    via = "openai_models"
                except Exception:
                    checked[-1]["error"] = "response was not JSON"
        if not endpoint_online and kind in ("auto", "http_status"):
            ok, _body, err = self._request(self.health_url(), None, timeout)
            checked.append({"endpoint": self.health_url(), "ok": ok, "error": err})
            if ok:
                endpoint_online = True
                via = "http_status"

        active = self.active_model_status(timeout=timeout) if self.selection_mode() == "ollama_active" else {
            "selection_mode": self.selection_mode(),
            "preferred_model": self.preferred_model(),
            "active_model": self.preferred_model() or "local-model",
            "loaded_models": [],
            "ok": True,
            "reason": "fixed",
            "message": "",
        }

        if not endpoint_online:
            return {
                "ok": False,
                "online": False,
                "model": active.get("active_model") or self.display_model(),
                "checked": checked,
                "active": active,
                "message": "The configured model endpoint is not responding. "
                           "Check Settings → Model endpoint.",
            }

        if self.selection_mode() == "ollama_active" and not active.get("ok"):
            return {
                "ok": False,
                "online": False,
                "model": active.get("active_model") or "",
                "checked": checked,
                "active": active,
                "via": via,
                "message": active.get("message")
                or "No usable active Ollama model is available.",
            }

        return {
            "ok": True,
            "online": True,
            "model": active.get("active_model") or self.display_model(),
            "checked": checked,
            "active": active,
            "via": via,
        }

    def advertised_capabilities(self, timeout: float = 5.0) -> Dict[str, Any]:
        """Read *advertised* OpenAI model metadata, without running inference.

        Model servers frequently omit capabilities. We report unknown rather
        than infer from a model name, and do not modify config or context.
        This is an optional, read-only diagnostic request.
        """
        ok, body, error = self._request(self.base_url() + "/v1/models", None, timeout)
        if not ok:
            return {
                "ok": False,
                "message": "Model metadata is unavailable: " + error,
                "model": self.model_name(),
                "settings_changed": False,
            }
        try:
            data = json.loads(body)
        except (ValueError, TypeError):
            return {"ok": False, "message": "The models endpoint did not return valid JSON.",
                    "settings_changed": False}
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            return {"ok": False, "message": "The models endpoint returned no model list.",
                    "settings_changed": False}
        records = [m for m in data["data"] if isinstance(m, dict) and isinstance(m.get("id"), str)]
        names = [m["id"] for m in records]
        target = next((m for m in records if m["id"] == self.model_name()), None)

        def declared_bool(record: Dict[str, Any], keys) -> bool | None:
            nested = record.get("capabilities")
            if not isinstance(nested, dict):
                nested = {}
            for key in keys:
                for obj in (record, nested):
                    value = obj.get(key)
                    if type(value) is bool:
                        return value
            return None

        window = None
        if target is not None:
            for key in ("context_length", "context_window", "max_model_len",
                        "max_context_length", "n_ctx"):
                value = target.get(key)
                if type(value) is int and value > 0:
                    window = value
                    break
        return {
            "ok": True, "source": "GET /v1/models",
            "model": self.model_name(),
            "model_found": target is not None,
            "advertised_models": names,
            "advertised_model_count": len(names),
            "declared_context_window": window,
            "declared_tool_calling": (
                declared_bool(target, ("tool_calling", "supports_tool_calls",
                                       "tools", "function_calling"))
                if target is not None else None
            ),
            "declared_vision": (
                declared_bool(target, ("vision", "supports_vision",
                                       "image_input"))
                if target is not None else None
            ),
            "declared_streaming": (
                declared_bool(target, ("streaming", "supports_streaming"))
                if target is not None else None
            ),
            "settings_changed": False,
            "note": (
                "Only capabilities explicitly advertised by the endpoint are shown. "
                "Unknown means not reported, not unsupported. No model was loaded "
                "and no context or timeout setting was changed."
            ),
        }

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 900,
             temperature: float = 0.82) -> Dict[str, Any]:
        """One chat completion. Resolves the active model immediately before calling."""
        resolved = self.resolve_model(timeout=3.0)
        if not resolved.get("ok"):
            return {
                "ok": False,
                "message": resolved.get("message")
                or "No active Ollama model is available for writing.",
                "loaded_models": resolved.get("loaded_models") or [],
            }
        model = str(resolved["model"])
        payload = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "stream": False,
        }
        if self.disable_thinking():
            payload["think"] = False
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
        return {"ok": True, "text": content, "model_name": model}


    def stream_chat(self, messages: List[Dict[str, str]], max_tokens: int = 900,
                    temperature: float = 0.82,
                    cancellation: Cancellation | None = None) -> Iterator[Dict[str, Any]]:
        """Yield {type: token|done|cancelled|error, ...} from OpenAI SSE.

        Uses the configured endpoint and timeout unchanged. A separate
        cancellation token can terminate the active upstream connection.
        Never writes or saves author text.
        """
        token = cancellation or Cancellation()
        resolved = self.resolve_model(timeout=3.0)
        if not resolved.get("ok"):
            yield {
                "type": "error",
                "message": resolved.get("message")
                or "No active Ollama model is available for writing.",
            }
            return
        payload = {
            "model": str(resolved["model"]),
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "stream": True,
        }
        if self.disable_thinking():
            payload["think"] = False
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if self.cfg.api_key():
            headers["Authorization"] = f"Bearer {self.cfg.api_key()}"
        req = urllib.request.Request(self.chat_url(),
                data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        if token.cancelled():
            yield {"type": "cancelled"}
            return
        response = None
        finished = False
        terminal = False
        saw_finish = False
        try:
            response = urllib.request.urlopen(req, timeout=self.timeout())
            token.bind(response)
            if token.cancelled():
                yield {"type": "cancelled"}
                terminal = True
                return
            media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if media_type != "text/event-stream":
                yield {"type": "error", "message": "Model endpoint did not return a streaming SSE response."}
                terminal = True
                return
            parts = []
            event_type = ""
            while not terminal:
                if token.cancelled():
                    yield {"type": "cancelled"}
                    terminal = True
                    break
                line = response.readline(1024 * 1024 + 1)
                if len(line) > 1024 * 1024:
                    raise ValueError("Model streaming event exceeded 1 MiB")
                if not line:
                    if parts:
                        # Tolerate a last SSE frame without an empty separator.
                        frame = "\n".join(parts)
                        parts = []
                    else:
                        break
                else:
                    line = line.decode("utf-8", errors="strict").rstrip("\r\n")
                    if line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        parts.append(line[5:].lstrip(" "))
                        continue
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                        continue
                    if line:
                        continue
                    if not parts:
                        event_type = ""
                        continue
                    frame = "\n".join(parts)
                    parts = []
                if frame == "[DONE]":
                    finished = True
                    terminal = True
                    break
                try:
                    event = json.loads(frame)
                except (ValueError, TypeError) as exc:
                    raise ValueError("Invalid JSON in model SSE response") from exc
                if event_type == "error" or (isinstance(event, dict) and "error" in event):
                    err = event.get("error", event) if isinstance(event, dict) else event
                    detail = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    yield {"type": "error", "message": str(detail)[:400]}
                    terminal = True
                    break
                if not isinstance(event, dict):
                    raise ValueError("Unrecognized model streaming frame")
                choices = event.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content") or ""
                    if isinstance(content, list):
                        content = "".join(str(p.get("text", "")) for p in content
                                          if isinstance(p, dict) and p.get("type") == "text")
                    if isinstance(content, str) and content:
                        yield {"type": "token", "text": content}
                    if choices[0].get("finish_reason") is not None:
                        saw_finish = True
                event_type = ""
            if token.cancelled():
                if not terminal:
                    yield {"type": "cancelled"}
            elif not terminal:
                if saw_finish:
                    finished = True
                else:
                    yield {"type": "error", "message": "Model stream ended before completion."}
            if finished and not token.cancelled():
                yield {"type": "done"}
            elif finished and token.cancelled():
                yield {"type": "cancelled"}
        except (urllib.error.URLError, OSError, ValueError, UnicodeError, AttributeError) as exc:
            if token.cancelled():
                yield {"type": "cancelled"}
            else:
                yield {"type": "error", "message": f"Model stream failed: {type(exc).__name__}: {exc}"}
        finally:
            if response is not None:
                token.release(response)
                try:
                    response.close()
                except (OSError, ValueError):
                    pass
