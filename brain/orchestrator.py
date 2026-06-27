"""Multi-provider AI conversation orchestrator.

Fallback chain: Gemini (primary) → OpenRouter → Groq
"""

import asyncio
import json
import threading
import time
import traceback
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE_DIR = _get_base_dir()
_API_CONFIG_PATH = _BASE_DIR / "config" / "api_keys.json"


def _load_keys() -> dict:
    try:
        return json.loads(_API_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_keys(data: dict):
    try:
        _API_CONFIG_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        print(f"[Brain] Failed to save keys: {e}")


class ProviderState:
    ACTIVE = "active"
    FAILED = "failed"
    RECOVERING = "recovering"


import sys


class ConversationProvider:
    def __init__(self, name: str):
        self.name = name
        self.state = ProviderState.ACTIVE
        self._lock = threading.Lock()

    def mark_failed(self):
        with self._lock:
            self.state = ProviderState.FAILED

    def mark_recovering(self):
        with self._lock:
            self.state = ProviderState.RECOVERING

    def mark_active(self):
        with self._lock:
            self.state = ProviderState.ACTIVE

    def is_available(self) -> bool:
        with self._lock:
            return self.state == ProviderState.ACTIVE


class Orchestrator:
    def __init__(self, ui, speak_fn):
        self.ui = ui
        self.speak = speak_fn
        self._current_provider: ConversationProvider | None = None
        self._loop = None
        self._history: list[dict] = []
        self._running = True

        self._gemini_connected = False
        self._gemini_lock = threading.Lock()
        self._reconnect_timer: threading.Thread | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    @property
    def gemini_connected(self) -> bool:
        with self._gemini_lock:
            return self._gemini_connected

    @gemini_connected.setter
    def gemini_connected(self, val: bool):
        with self._gemini_lock:
            self._gemini_connected = val

    def chat(self, text: str) -> str:
        keys = _load_keys()
        preferred = keys.get("preferred_provider", "gemini").lower()

        if preferred == "openrouter":
            chain = ["openrouter", "groq", "gemini"]
        elif preferred == "groq":
            chain = ["groq", "openrouter", "gemini"]
        else:
            chain = ["gemini", "openrouter", "groq"]

        for provider_name in chain:
            try:
                result = self._call_provider(provider_name, text, keys)
                if result:
                    self._history.append({"role": "user", "text": text})
                    self._history.append({"role": "assistant", "text": result})
                    if len(self._history) > 40:
                        self._history = self._history[-40:]
                    return result
            except Exception as e:
                print(f"[Brain] {provider_name} failed: {e}")
                continue

        return "All providers are currently unavailable."

    def _call_provider(self, name: str, text: str, keys: dict) -> str | None:
        from groq_client import GroqClient
        from memory.config_manager import get_openrouter_key, get_groq_key
        from or_client import client as or_client

        if name == "openrouter":
            key = get_openrouter_key()
            if not key:
                return None
            try:
                resp = or_client.chat([
                    {"role": "system", "content": "You are VAYU, a sharp AI assistant. Be concise."},
                    *[{"role": m["role"], "content": m["text"]} for m in self._history[-10:]],
                    {"role": "user", "content": text},
                ])
                return resp if resp else None
            except Exception as e:
                print(f"[Brain] OpenRouter chat error: {e}")
                return None

        elif name == "groq":
            key = get_groq_key()
            if not key:
                return None
            try:
                gc = GroqClient(api_key=key)
                resp = gc.chat(
                    system="You are VAYU, a sharp AI assistant. Be concise.",
                    messages=[{"role": m["role"], "content": m["text"]} for m in self._history[-10:]],
                    user_msg=text,
                )
                return resp if resp else None
            except Exception as e:
                print(f"[Brain] Groq chat error: {e}")
                return None

        return None
