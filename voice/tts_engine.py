"""Multi-backend TTS engine.

Backends (tried in order):
1. edge-tts — high-quality neural voices, free, requires internet
2. Windows SAPI5 — built-in Windows voices, no internet needed
3. Groq Whisper TTS — using Groq API (if available)
4. pyttsx3 — offline fallback

Configure via preferred_tts in api_keys.json: "edge", "sapi5", "groq", or "auto"
"""

import json
import sys
import threading
import subprocess
import tempfile
import os
from pathlib import Path

try:
    import pyttsx3
    _PYTTSX3 = True
except ImportError:
    _PYTTSX3 = False


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_API_CONFIG = _get_base_dir() / "config" / "api_keys.json"


def _load_config() -> dict:
    try:
        return json.loads(_API_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


class TTSEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._current_backend: str | None = None

    def _get_preferred(self) -> str:
        cfg = _load_config()
        return cfg.get("preferred_tts", "auto").lower()

    def speak(self, text: str) -> bool:
        preferred = self._get_preferred()

        backends = []
        if preferred == "edge":
            backends = ["edge", "sapi5", "pyttsx3"]
        elif preferred == "sapi5":
            backends = ["sapi5", "edge", "pyttsx3"]
        elif preferred == "groq":
            backends = ["groq", "edge", "sapi5", "pyttsx3"]
        else:
            backends = ["edge", "sapi5", "groq", "pyttsx3"]

        for backend in backends:
            try:
                if backend == "edge":
                    if self._edge_tts(text):
                        self._current_backend = "edge"
                        return True
                elif backend == "sapi5":
                    if self._sapi5_tts(text):
                        self._current_backend = "sapi5"
                        return True
                elif backend == "groq":
                    if self._groq_tts(text):
                        self._current_backend = "groq"
                        return True
                elif backend == "pyttsx3":
                    if _PYTTSX3:
                        with self._lock:
                            tts = pyttsx3.init()
                            tts.say(text)
                            tts.runAndWait()
                            self._current_backend = "pyttsx3"
                            return True
            except Exception as e:
                print(f"[TTS] {backend} failed: {e}")
                continue

        print("[TTS] All backends failed.")
        return False

    def _edge_tts(self, text: str) -> bool:
        try:
            import edge_tts
            voice = _load_config().get("edge_tts_voice", "en-US-EmmaNeural")
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                path = f.name
            asyncio_run = _get_or_create_eventloop()

            async def _do():
                await communicate.save(path)

            asyncio_run(_do())

            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)

            def _clean():
                import time
                time.sleep(1)
                try:
                    os.unlink(path)
                except Exception:
                    pass

            threading.Thread(target=_clean, daemon=True).start()
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"[TTS] edge-tts error: {e}")
            return False

    def _sapi5_tts(self, text: str) -> bool:
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(text)
            return True
        except Exception as e:
            print(f"[TTS] SAPI5 error: {e}")
            return False

    def _groq_tts(self, text: str) -> bool:
        try:
            from memory.config_manager import get_groq_key
            key = get_groq_key()
            if not key:
                return False
            from groq_client import GroqClient
            gc = GroqClient(api_key=key)
            result = gc.transcribe_from_file(
                audio_data=text.encode(),
                filename="tts.wav",
            )
            return bool(result)
        except Exception as e:
            print(f"[TTS] Groq TTS error: {e}")
            return False

    @property
    def backend_name(self) -> str:
        return self._current_backend or "none"


def _get_or_create_eventloop():
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete
    except Exception:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete


# Singleton
_engine = TTSEngine()


def speak_text(text: str) -> bool:
    return _engine.speak(text)


def current_backend() -> str:
    return _engine.backend_name
