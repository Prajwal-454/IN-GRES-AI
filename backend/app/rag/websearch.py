"""Keyless web search fallback for questions the knowledge base can't answer.

Uses the DuckDuckGo text search via the ``ddgs`` package — no API key, no
account. Results are plain ``{title, url, snippet}`` dicts that get passed to
the LLM as extra context; the model must cite them. Any failure returns an
empty list so the assistant degrades gracefully to its normal behaviour.
"""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def search(query: str, max_results: int | None = None) -> list[dict]:
    """Web search results, or [] when disabled / offline / no hits."""
    settings = get_settings()
    if not settings.WEB_SEARCH_ENABLED:
        return []
    limit = max_results or settings.WEB_SEARCH_MAX_RESULTS
    try:
        from ddgs import DDGS

        with DDGS(timeout=settings.WEB_SEARCH_TIMEOUT_SECONDS) as ddgs:
            rows = ddgs.text(query, max_results=limit)
            return [
                {"title": r.get("title", ""), "url": r.get("href", ""),
                 "snippet": r.get("body", "")}
                for r in rows
                if r.get("href")
            ]
    except Exception as exc:  # noqa: BLE001 - web search is best-effort
        logger.warning("web search failed (continuing without it): %s", exc)
        return []
