import json
import sys
import time
import base64
import logging
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("groq_client")

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR     = _get_base_dir()
API_KEY_PATH = BASE_DIR / "config" / "api_keys.json"

def _load_api_key() -> str:
    try:
        with open(API_KEY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        key = data.get("groq_api_key", "").strip()
        if not key:
            raise ValueError("groq_api_key is empty in api_keys.json")
        return key
    except FileNotFoundError:
        raise RuntimeError(f"api_keys.json not found at: {API_KEY_PATH}")
    except Exception as e:
        raise RuntimeError(f"Failed to load Groq API key: {e}")

TEXT_MODELS: list[str] = [
    "llama-3.3-70b-versatile",
    "llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

WHISPER_MODELS: list[str] = [
    "whisper-large-v3",
    "whisper-large-v3-turbo",
]

API_URL               = "https://api.groq.com/openai/v1/chat/completions"
AUDIO_API_URL         = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_MAX_TOKENS    = 4096
DEFAULT_TEMPERATURE   = 0.7
REQUEST_TIMEOUT       = 60
MAX_RETRIES_PER_MODEL = 2
RETRY_DELAY           = 2
RATE_LIMIT_COOLDOWN   = 60

_rate_limited: dict[str, float] = {}

class GroqClient:

    def __init__(self) -> None:
        self.api_key  = _load_api_key()
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    def _is_rate_limited(self, model: str) -> bool:
        ts = _rate_limited.get(model)
        if ts is None:
            return False
        if time.time() - ts > RATE_LIMIT_COOLDOWN:
            del _rate_limited[model]
            return False
        return True

    def _mark_rate_limited(self, model: str) -> None:
        _rate_limited[model] = time.time()
        logger.warning(
            f"[Groq] Rate limited: {model} \u2014 "
            f"cooling down for {RATE_LIMIT_COOLDOWN}s"
        )

    def _call(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        payload: dict = {
            "model":       model,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = {"type": "json_object"}

        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            try:
                resp = requests.post(
                    API_URL,
                    headers=self._headers,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )

                if resp.status_code == 429:
                    self._mark_rate_limited(model)
                    return None

                if resp.status_code == 200:
                    data    = resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                    )
                    return content.strip() if content else None

                logger.warning(
                    f"[Groq] {model} \u2192 HTTP {resp.status_code} "
                    f"(attempt {attempt}/{MAX_RETRIES_PER_MODEL})"
                )

            except requests.exceptions.Timeout:
                logger.warning(
                    f"[Groq] {model} \u2192 Timeout "
                    f"(attempt {attempt}/{MAX_RETRIES_PER_MODEL})"
                )
            except Exception as e:
                logger.error(f"[Groq] {model} \u2192 Unexpected error: {e}")

            if attempt < MAX_RETRIES_PER_MODEL:
                time.sleep(RETRY_DELAY)

        return None

    def _call_with_fallback(
        self,
        pool: list[str],
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        response_format: Optional[dict] = None,
    ) -> str:
        if model and not self._is_rate_limited(model):
            result = self._call(model, messages, max_tokens, temperature, response_format)
            if result:
                return result
            logger.info(
                f"[Groq] Requested model failed, "
                f"falling back to pool: {model}"
            )

        for m in pool:
            if self._is_rate_limited(m):
                continue
            logger.info(f"[Groq] Trying: {m}")
            result = self._call(m, messages, max_tokens, temperature, response_format)
            if result:
                logger.info(f"[Groq] \u2713 Success: {m}")
                return result

        raise RuntimeError(
            "[Groq] All models failed or are rate-limited. "
            "Check your API key and network connection."
        )

    def chat(
        self,
        prompt: str,
        system: str = (
            "You are a component of VAYU, a powerful AI assistant. "
            "Be concise, helpful, and precise."
        ),
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]
        return self._call_with_fallback(
            TEXT_MODELS, messages, model, max_tokens, temperature
        )

    def chat_json(
        self,
        prompt: str,
        system: str = (
            "Return ONLY valid JSON. "
            "No markdown fences, no extra text, no explanation."
        ),
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]
        raw = self._call_with_fallback(
            TEXT_MODELS, messages, model, max_tokens, temperature=0.2,
            response_format={"type": "json_object"}
        )

        clean = raw.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("`").strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(
                f"[Groq] JSON parse failed: {e}\n"
                f"Raw response (first 300 chars): {raw[:300]}"
            )
            raise ValueError(
                f"Groq model returned unparseable JSON: {e}\n"
                f"Raw output: {raw[:200]}"
            )

    def multi_turn(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        return self._call_with_fallback(
            TEXT_MODELS, messages, model, max_tokens, temperature
        )

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        model: Optional[str] = None,
        language: Optional[str] = None,
    ) -> str:
        models = WHISPER_MODELS
        if model:
            models = [model] + [m for m in WHISPER_MODELS if m != model]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        for m in models:
            if self._is_rate_limited(m):
                continue
            try:
                files = {
                    "file": (filename, audio_bytes, "audio/wav"),
                    "model": (None, m),
                }
                if language:
                    files["language"] = (None, language)

                resp = requests.post(
                    AUDIO_API_URL,
                    headers=headers,
                    files=files,
                    timeout=REQUEST_TIMEOUT,
                )

                if resp.status_code == 429:
                    self._mark_rate_limited(m)
                    continue

                if resp.status_code == 200:
                    text = resp.json().get("text", "").strip()
                    if text:
                        logger.info(f"[Groq] \u2713 Transcribed with {m}")
                        return text

                logger.warning(
                    f"[Groq] Transcription {m} \u2192 HTTP {resp.status_code}"
                )

            except Exception as e:
                logger.error(f"[Groq] Transcription {m} failed: {e}")

        raise RuntimeError("[Groq] All Whisper models failed for transcription.")

    def transcribe_from_file(
        self,
        audio_path: str,
        model: Optional[str] = None,
        language: Optional[str] = None,
    ) -> str:
        path = Path(audio_path)
        with open(path, "rb") as f:
            audio_bytes = f.read()
        return self.transcribe(audio_bytes, path.name, model, language)

    def available_models(self) -> dict:
        return {
            "text_models":   TEXT_MODELS,
            "whisper_models": WHISPER_MODELS,
            "rate_limited":  list(_rate_limited.keys()),
            "total_text":    len(TEXT_MODELS),
            "total_whisper": len(WHISPER_MODELS),
        }

client = GroqClient()

def _ok(x=""): return f"[OK] {x}" if x else "[OK]"
def _fail(x=""): return f"[FAIL] {x}" if x else "[FAIL]"

if __name__ == "__main__":
    print("=" * 55)
    print("  VAYU -- Groq Client Self-Test")
    print("=" * 55)

    print("\n[TEST 1] Basic chat...")
    try:
        reply = client.chat("Introduce yourself in one sentence.")
        print(f"  Response : {reply}")
        print(f"  Status   : {_ok()}")
    except Exception as e:
        print(f"  Status   : {_fail(e)}")

    print("\n[TEST 2] JSON mode...")
    try:
        data = client.chat_json(
            'List 3 programming languages. Format: {"languages": ["a", "b", "c"]}',
            system="Return only valid JSON. No extra text."
        )
        print(f"  Response : {data}")
        print(f"  Status   : {_ok()}")
    except Exception as e:
        print(f"  Status   : {_fail(e)}")

    print("\n[TEST 3] Multi-turn conversation...")
    try:
        history = [
            {"role": "system",    "content": "You are a helpful assistant. Be brief."},
            {"role": "user",      "content": "My name is the user."},
            {"role": "assistant", "content": "Hello the user, how can I help you?"},
            {"role": "user",      "content": "What is my name?"},
        ]
        reply = client.multi_turn(history)
        print(f"  Response : {reply}")
        print(f"  Status   : {_ok()}")
    except Exception as e:
        print(f"  Status   : {_fail(e)}")

    print("\n[TEST 4] Model pool info...")
    info = client.available_models()
    print(f"  Text models   : {info['total_text']}")
    print(f"  Whisper models: {info['total_whisper']}")
    print(f"  Rate limited  : {info['rate_limited'] or 'none'}")
    print(f"  Status        : {_ok()}")

    print("\n" + "=" * 55)
    print("  All tests complete.")
    print("=" * 55)
