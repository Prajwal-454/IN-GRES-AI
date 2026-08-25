"""Tests for semantic RAG embeddings and the RAG API."""

import io
import os

from app.rag.embeddings import cosine_similarity, local_embed
from app.rag.retriever import reindex_embeddings


def _json(client, token, method, url, **kwargs):
    kwargs.setdefault("headers", {"Authorization": f"Bearer {token}"})
    return getattr(client, method)(url, **kwargs)


def test_local_embed_deterministic_and_normalised():
    a = local_embed("groundwater recharge aquifer")
    b = local_embed("groundwater recharge aquifer")
    assert a == b
    norm = (sum(v * v for v in a)) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_cosine_similarity_overlap():
    a = local_embed("what is an aquifer")
    b = local_embed("aquifer definition")
    c = local_embed("quantum computing coffee")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)


def test_rag_status_reports_embeddings(client, user_token):
    resp = _json(client, user_token, "get", "/api/rag/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["mode"] in ("bm25", "vector", "hybrid")
    assert data["chunks"] > 0


def test_rag_search_hybrid(client, user_token):
    resp = _json(client, user_token, "get", "/api/rag/search?q=recharge&top_k=2")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert len(body["results"]) <= 2
    for r in body["results"]:
        assert "content" in r and "score" in r


def test_rag_reindex_admin_only(client, user_token, admin_token):
    # Non-admin is forbidden.
    resp = _json(client, user_token, "post", "/api/rag/reindex")
    assert resp.status_code == 403
    # Admin can re-embed.
    resp = _json(client, admin_token, "post", "/api/rag/reindex")
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == body["chunks"]
    assert body["indexed"] == body["chunks"]
