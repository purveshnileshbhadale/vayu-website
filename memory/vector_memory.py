"""Vector memory — semantic search over conversations and stored memories.

Uses lightweight TF-IDF + cosine similarity (no heavy ML dependencies).
Falls back to keyword search if embeddings unavailable.
"""

import json
import math
import re
import sys
from pathlib import Path
from collections import Counter


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE = _get_base_dir()
_MEMORY_PATH = _BASE / "memory" / "long_term.json"
_CONV_DB = _BASE / "memory" / "conversations.db"


# ----- TF-IDF vectorizer (lightweight, no external deps) -----

_token_cache: dict[str, list[str]] = {}


def _tokenize(text: str) -> list[str]:
    if text in _token_cache:
        return _token_cache[text]
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    _token_cache[text] = tokens
    return tokens


class _TfidfIndex:
    def __init__(self):
        self.docs: list[dict] = []
        self._idf: dict[str, float] = {}
        self._doc_vectors: list[dict[str, float]] = []
        self._built = False

    def add(self, text: str, meta: dict):
        self.docs.append({"text": text, "meta": meta})
        self._built = False

    def build(self):
        N = len(self.docs)
        if N == 0:
            return
        df: Counter = Counter()
        all_tokens = []
        for d in self.docs:
            toks = set(_tokenize(d["text"]))
            df.update(toks)
            all_tokens.append(toks)

        self._idf = {t: math.log(N / (1 + c)) for t, c in df.items()}
        self._doc_vectors = []
        for toks in all_tokens:
            vec = {}
            for t in toks:
                vec[t] = self._idf.get(t, 0) * (1 + math.log(1 + toks.count(t)))
            self._doc_vectors.append(vec)
        self._built = True

    def _cosine(self, a: dict[str, float], b: dict[str, float]) -> float:
        keys = set(a) | set(b)
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._built:
            self.build()
        if not self._built or not self.docs:
            return []

        q_toks = _tokenize(query)
        q_vec = {}
        for t in q_toks:
            q_vec[t] = self._idf.get(t, 0) * (1 + math.log(1 + q_toks.count(t)))

        scored = [(self._cosine(q_vec, dv), i)
                  for i, dv in enumerate(self._doc_vectors)]
        scored.sort(key=lambda x: -x[0])

        results = []
        for score, idx in scored[:top_k]:
            if score > 0:
                results.append({**self.docs[idx], "score": round(score, 3)})
        return results


# ----- Main API -----

_index = _TfidfIndex()
_index_loaded = False


def _load_memory_texts() -> list[str]:
    texts = []
    try:
        if _MEMORY_PATH.exists():
            data = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            for cat, items in data.items():
                if isinstance(items, dict):
                    for key, val in items.items():
                        if isinstance(val, dict) and "value" in val:
                            texts.append(f"{cat}: {key} = {val['value']}")
                        elif isinstance(val, str):
                            texts.append(f"{cat}: {key} = {val}")
    except Exception:
        pass
    return texts


def _load_conversation_texts() -> list[str]:
    texts = []
    try:
        if _CONV_DB.exists():
            import sqlite3
            conn = sqlite3.connect(str(_CONV_DB))
            rows = conn.execute(
                "SELECT role, content FROM conversations ORDER BY id DESC LIMIT 200"
            ).fetchall()
            conn.close()
            for role, content in rows:
                texts.append(f"[{role}] {content[:500]}")
    except Exception:
        pass
    return texts


def rebuild_index():
    global _index, _index_loaded
    _index = _TfidfIndex()
    _index_loaded = False

    for t in _load_memory_texts():
        _index.add(t, {"type": "memory"})
    for t in _load_conversation_texts():
        _index.add(t, {"type": "conversation"})

    _index.build()
    _index_loaded = True
    print(f"[VectorMemory] Index built: {len(_index.docs)} docs")


def semantic_search(query: str, top_k: int = 5) -> list[dict]:
    global _index_loaded
    if not _index_loaded:
        rebuild_index()
    return _index.search(query, top_k)


def format_search_results(results: list[dict]) -> str:
    if not results:
        return "No relevant memories found."
    lines = []
    for r in results:
        tag = r["meta"].get("type", "?").upper()
        text = r["text"][:150]
        lines.append(f"[{tag}] ({r['score']}) {text}")
    return "\n".join(lines)
