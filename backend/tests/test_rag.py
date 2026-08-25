from fastapi.testclient import TestClient


def test_rag_status(client: TestClient, auth_user):
    resp = client.get("/api/rag/status", headers=auth_user)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "chunks" in body or "available" in body


def test_rag_ingest(client: TestClient, auth_user):
    resp = client.post("/api/rag/ingest", headers=auth_user)
    assert resp.status_code == 200, resp.text
    assert resp.json()["chunks"] > 0


def test_rag_search(client: TestClient, auth_user):
    resp = client.get(
        "/api/rag/search", params={"q": "aquifer"}, headers=auth_user
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert len(results) > 0
    assert "content" in results[0]
    assert "document_title" in results[0]
    assert "score" in results[0]


def test_rag_search_detailed_metadata(client: TestClient, auth_user):
    resp = client.get(
        "/api/rag/search", params={"q": "recharge"}, headers=auth_user
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["results"][0]
    assert result["document_title"] is not None
    assert result["document_id"] is not None


def test_rag_documents_list(client: TestClient, auth_user):
    resp = client.get("/api/rag/documents", headers=auth_user)
    assert resp.status_code == 200, resp.text
    docs = resp.json()["documents"]
    assert len(docs) > 0
    assert "title" in docs[0]
    assert "chunk_count" in docs[0]


def test_rag_upload_and_delete_requires_admin(client: TestClient, auth_user):
    resp = client.post(
        "/api/rag/documents",
        files={"file": ("notes.md", b"# Test\n\n" + b"Groundwater recharge is water that percolates into aquifers. " * 10, "text/markdown")},
        headers=auth_user,
    )
    assert resp.status_code == 403


def test_rag_upload_and_delete_admin(client: TestClient, auth_admin, auth_user):
    payload = (
        "# Test document\n\n"
        + ("Groundwater conservation means using water carefully to protect aquifers. " * 12)
    )
    resp = client.post(
        "/api/rag/documents",
        files={"file": ("test-conservation.md", payload.encode(), "text/markdown")},
        headers=auth_admin,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"]
    doc = next(d for d in body["documents"] if d["title"] == body["title"])

    resp = client.delete(f"/api/rag/documents/{doc['id']}", headers=auth_admin)
    assert resp.status_code == 204

    resp = client.get("/api/rag/documents", headers=auth_user)
    titles = [d["title"] for d in resp.json()["documents"]]
    assert body["title"] not in titles