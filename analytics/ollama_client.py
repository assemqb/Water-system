"""
Local Ollama LLM client for the Environmental Intelligence Analyst.

Uses the Ollama HTTP API (stdlib only — no ollama Python package required).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from config.settings import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_PREFERRED_MODELS, OLLAMA_TIMEOUT

_UNAVAILABLE: str | None = None
_RESOLVED_MODEL: str | None = None


def _base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", OLLAMA_BASE_URL).rstrip("/")


def _http_get(path: str, timeout: float = 5.0) -> dict[str, Any] | None:
    req = urllib.request.Request(f"{_base_url()}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def list_models() -> list[str]:
    """Return installed model names from Ollama."""
    data = _http_get("/api/tags")
    if not data:
        return []
    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]


def resolve_model() -> str | None:
    """Pick the best available model: env override, then preferred list, then first installed."""
    global _RESOLVED_MODEL
    if _RESOLVED_MODEL:
        return _RESOLVED_MODEL

    env_model = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL).strip()
    installed = list_models()
    if not installed:
        return None

    if env_model:
        for name in installed:
            if name == env_model or name.startswith(f"{env_model}:"):
                _RESOLVED_MODEL = name
                return _RESOLVED_MODEL

    for preferred in OLLAMA_PREFERRED_MODELS:
        for name in installed:
            base = name.split(":")[0]
            if base == preferred or name.startswith(f"{preferred}:"):
                _RESOLVED_MODEL = name
                return _RESOLVED_MODEL

    _RESOLVED_MODEL = installed[0]
    return _RESOLVED_MODEL


def is_available() -> bool:
    """True when Ollama responds and at least one model is installed."""
    global _UNAVAILABLE
    if _UNAVAILABLE == "checked":
        return resolve_model() is not None
    models = list_models()
    if models:
        _UNAVAILABLE = "checked"
        return True
    _UNAVAILABLE = "checked"
    return False


def reset_cache() -> None:
    """Clear cached availability/model (for tests)."""
    global _UNAVAILABLE, _RESOLVED_MODEL
    _UNAVAILABLE = None
    _RESOLVED_MODEL = None


def generate(system: str, user: str, lang: str = "en") -> tuple[str | None, str | None]:
    """
    Send a chat completion to Ollama.

    Returns (content, model_name) or (None, None) on failure.
    """
    model = resolve_model()
    if not model:
        return None, None

    payload = json.dumps({
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.35, "num_predict": 600},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{_base_url()}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            content = data.get("message", {}).get("content", "").strip()
            return (content or None), model
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, OSError):
        return None, None
