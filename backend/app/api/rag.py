"""RAG status, knowledge-base search and document-management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.config import get_settings
from app.core.audit import write_audit
from app.database import get_db
from app.models.user import User
from app.rag.retriever import (
    add_document,
    available,
    chunk_count,
    delete_document,
    indexed_count,
    ingest,
    list_documents,
    reindex_embeddings,
    search_detailed,
)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/status")
def rag_status(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    settings = get_settings()
    return {
        "enabled": True,
        "available": available(),
        "chunks": chunk_count(db),
        "indexed": indexed_count(db),
        "mode": settings.RAG_MODE,
        "embedding_enabled": settings.EMBEDDING_ENABLED,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dim": settings.EMBEDDING_DIM,
    }


@router.post("/ingest")
def rag_ingest(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    added = ingest(db)
    return {"added": added, "chunks": chunk_count(db), "indexed": indexed_count(db)}


@router.post("/reindex")
def rag_reindex(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin")),
):
    updated = reindex_embeddings(db)
    return {"updated": updated, "chunks": chunk_count(db), "indexed": indexed_count(db)}


@router.get("/documents")
def rag_documents(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return {"documents": list_documents(db)}


@router.post("/documents", status_code=status.HTTP_201_CREATED)
def rag_upload_document(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin")),
    file: UploadFile = File(...),
):
    """Upload a markdown document to the knowledge base (admin)."""
    content = file.file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Document exceeds 5 MB.")
    ok, message = add_document(db, file.filename or "upload.md", content, admin_user.id)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, message)
    write_audit(db, admin_user, "KNOWLEDGE_DOC_UPLOAD", "knowledge_document", None, {"title": message})
    return {"title": message, "documents": list_documents(db)}


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def rag_delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin")),
):
    if not delete_document(db, document_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    write_audit(db, admin_user, "KNOWLEDGE_DOC_DELETE", "knowledge_document", document_id, {})
    return None


@router.get("/search")
def rag_search(
    q: str = Query(min_length=2),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    results = search_detailed(db, q, top_k=top_k)
    return {"query": q, "results": results}
