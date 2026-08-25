"""In-process cache for expensive, read-only aggregate queries.

The national demo dataset is static and huge (millions of assessment rows),
so the aggregate endpoints (summary, trends, rankings) are memoised in-process
keyed by their filter arguments. Any code path that mutates assessment data
(seeds, CSV imports) must call :func:`invalidate_analytics_cache` so later
requests are recomputed from the new data.
"""

from __future__ import annotations

import threading

_CACHE: dict[tuple, object] = {}
_LOCK = threading.Lock()


def cache_get(key: tuple) -> object | None:
    return _CACHE.get(key)


def cache_set(key: tuple, value: object) -> object:
    with _LOCK:
        _CACHE[key] = value
    return value


def invalidate_analytics_cache() -> None:
    """Drop every cached aggregate so the next request recomputes."""
    with _LOCK:
        _CACHE.clear()