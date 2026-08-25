"""Embedding support for semantic RAG.

Produces a fixed-dimensional vector for a text passage. Two strategies are
supported:

1. Remote embeddings through an OpenAI-compatible ``/embeddings`` endpoint
   (e.g. Ollama with ``nomic-embed-text``). Used when ``EMBEDDING_ENABLED`` is
   true and the remote endpoint answers; otherwise we transparently fall back
   to the local hashing embedder so retrieval keeps working offline.
2. A dependency-free local hashing embedder: character 3-grams are hashed into
   a fixed-size bag-of-vector accumulator and L2-normalised. This captures
   sub-word overlap (so typo-tolerance and near-synonym sharing work) without
   any model download.

Everything is deterministic for a given dimension so indexes stay stable.
"""

from __future__ import annotations

import hashlib
import logging
import math

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# n-gram sizes used by the local embedder (1..4 covers words and sub-words).
_NGRAMS = (1, 2, 3)


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def local_embed(text: str, dim: int | None = None) -> list[float]:
    """Deterministic bag-of-n-gram hashing embedding, L2 normalised."""
    settings = get_settings()
    dim = dim or settings.EMBEDDING_DIM
    vec = [0.0] * dim
    cleaned = _normalise(text)
    if not cleaned:
        return vec

    tokens = []
    for word in cleaned.replace("-", " ").split():
        if word:
            tokens.append(word)
    if not tokens:
        tokens = [cleaned]

    for token in tokens:
        for n in _NGRAMS:
            if len(token) < n:
                continue
            for i in range(len(token) - n + 1):
                gram = token[i : i + n]
                h = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16)
                vec[h % dim] += 1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _remote_embed(texts: list[str]) -> list[list[float]] | None:
    """Embed via OpenAI-compatible /embeddings. Returns None on any failure."""
    settings = get_settings()
    payload = {"model": settings.EMBEDDING_MODEL, "input": texts}
    try:
        with httpx.Client(timeout=settings.EMBEDDING_TIMEOUT_SECONDS) as client:
            if "11434" in settings.resolved_llm_base_url():
                payload["keep_alive"] = "30m"
            resp = client.post(
                f"{settings.resolved_llm_base_url()}/embeddings",
                json=payload,
                headers={"Authorization": f"Bearer {settings.resolved_llm_api_key()}"},
            )
            resp.raise_for_status()
            data = resp.json()
            ordered = sorted(data["data"], key=lambda d: d.get("index", 0))
            return [d["embedding"] for d in ordered]
    except Exception as exc:  # noqa: BLE001 - remote embedding is optional
        logger.warning("remote embedding failed, using local embedder: %s", exc)
        return None


def embed(text: str) -> list[float]:
    """Embed a single text. Prefers remote when available, else local hash."""
    if _remote_available():
        remote = _remote_embed([text])
        if remote:
            return remote[0]
    return local_embed(text)


def _remote_available() -> bool:
    settings = get_settings()
    return settings.LLM_ENABLED and settings.EMBEDDING_ENABLED


def embed_many(texts: list[str]) -> list[list[float]]:
    """Embed many texts in one remote call if possible, else locally."""
    if _remote_available() and texts:
        remote = _remote_embed(texts)
        if remote:
            return remote
    return [local_embed(t) for t in texts]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors (0.0 on empty)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)