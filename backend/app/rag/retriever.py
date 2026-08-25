"""Retrieval-Augmented Generation (RAG) support.

Ingests markdown knowledge documents into `knowledge_documents` /
`knowledge_chunks`, computes an embedding per chunk, and provides retrieval
that is either BM25, semantic (cosine over embeddings), or a hybrid of both —
controlled by the `RAG_MODE` setting (`bm25` | `vector` | `hybrid`).

Data is never fabricated here: retrieval only returns verbatim text from
documents that are already stored in the knowledge base.
"""

from __future__ import annotations

import logging
import math
import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.rag import KnowledgeChunk, KnowledgeDocument
from app.rag.embeddings import cosine_similarity, embed, embed_many

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$")
_TOKEN_RE = re.compile(r"[a-zA-Z\u0C00-\u0C7F\u0900-\u097F0-9]+")
_MIN_CHUNK = 300
_MAX_CHUNK = 900


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _split_document(text: str) -> list[tuple[str, str | None]]:
    """Split a markdown document into (content, section) chunks."""
    chunks: list[tuple[str, str | None]] = []
    current_section: str | None = None
    current: list[str] = []

    def flush():
        nonlocal current
        body = " ".join(current).strip()
        if body:
            chunks.append((body, current_section))
        current = []

    for line in text.splitlines():
        stripped = line.strip()
        heading = _HEADING_RE.match(stripped)
        if heading:
            flush()
            current_section = heading.group(1).strip()
            continue
        if not stripped:
            flush()
            continue
        current.append(stripped)
        # Break very long single paragraphs at sentence-ish boundaries.
        while len(" ".join(current)) > _MAX_CHUNK:
            pieces = " ".join(current)
            cut = pieces.rfind(". ", 0, _MAX_CHUNK)
            if cut == -1:
                cut = _MAX_CHUNK
            chunks.append((pieces[: cut + 1].strip(), current_section))
            current = [pieces[cut + 1 :].strip()]

    flush()
    return [(c, s) for c, s in chunks if len(c) >= _MIN_CHUNK or len(chunks) == 1]


def ingest(db: Session) -> int:
    """Ingest markdown files from the knowledge directory if not already ingested.

    Returns the number of documents added.
    """
    docs_dir = get_settings().knowledge_dir
    if not docs_dir.is_dir():
        logger.warning("knowledge dir %s not found", docs_dir)
        return 0

    added = 0
    for path in sorted(docs_dir.glob("*.md")):
        title = path.stem.replace("-", " ").replace("_", " ").title()
        existing = db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.file_path == str(path))
        )
        if existing:
            continue

        text = path.read_text(encoding="utf-8")
        doc = KnowledgeDocument(
            title=title,
            source="IN-GRES AI knowledge base",
            author="IN-GRES AI",
            document_version="1.0",
            file_path=str(path),
            status="processed",
        )
        db.add(doc)
        db.flush()

        chunks: list[tuple[str, str | None]] = _split_document(text)
        embeddings = embed_many([c for c, _s in chunks]) if get_settings().EMBEDDING_ENABLED else []
        for index, (content, section) in enumerate(chunks):
            db.add(
                KnowledgeChunk(
                    document_id=doc.id,
                    chunk_index=index,
                    content=content,
                    section=section,
                    embedding=embeddings[index] if index < len(embeddings) else None,
                    embedding_model=get_settings().EMBEDDING_MODEL,
                )
            )
        added += 1

    if added:
        db.commit()
        logger.info("ingested %d knowledge document(s)", added)
    return added


def reindex_embeddings(db: Session) -> int:
    """(Re)compute embeddings for every chunk. Returns number updated."""
    chunks = list(db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.id)))
    if not chunks:
        return 0
    embeddings = embed_many([c.content for c in chunks])
    for chunk, vector in zip(chunks, embeddings):
        chunk.embedding = vector
        chunk.embedding_model = get_settings().EMBEDDING_MODEL
    db.commit()
    return len(chunks)


class BM25Index:
    def __init__(self, docs: list[str]):
        self.corpus = docs
        self.n = len(docs)
        self.k1 = 1.5
        self.b = 0.75
        self.doc_lengths = [len(_tokenize(d)) for d in docs]
        self.avgdl = sum(self.doc_lengths) / self.n if self.n else 0.0

        self.idf: dict[str, float] = {}
        df: dict[str, int] = {}
        for doc in docs:
            for token in set(_tokenize(doc)):
                df[token] = df.get(token, 0) + 1
        for token, freq in df.items():
            self.idf[token] = math.log(1 + (self.n - freq + 0.5) / (freq + 0.5))

    def search(self, query: str, top_k: int = 3) -> list[tuple[str, float]]:
        if self.n == 0:
            return []
        query_tokens = _tokenize(query)
        scored: list[tuple[int, float]] = []
        for i, doc in enumerate(self.corpus):
            dl = self.doc_lengths[i]
            tf: dict[str, int] = {}
            for token in _tokenize(doc):
                tf[token] = tf.get(token, 0) + 1
            score = 0.0
            for token in query_tokens:
                if token not in self.idf:
                    continue
                f = tf.get(token, 0)
                if f == 0:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl) if self.avgdl else f
                score += self.idf[token] * (f * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((i, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self.corpus[i], s) for i, s in scored[:top_k]]


_index: BM25Index | None = None
_index_db_key: str | None = None


def _load_index(db: Session) -> BM25Index:
    global _index, _index_db_key
    chunks = list(db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.id)))
    if not chunks:
        ingest(db)
        chunks = list(db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.id)))
    if not chunks:
        return BM25Index([])
    key = str(len(chunks))
    if _index is None or _index_db_key != key:
        _index = BM25Index([c.content for c in chunks])
        _index_db_key = key
    return _index


def _vector_search(chunks: list[KnowledgeChunk], query_embedding: list[float], top_k: int) -> list[tuple[str, float]]:
    scored: list[tuple[str, float]] = []
    for chunk in chunks:
        if not chunk.embedding:
            continue
        score = cosine_similarity(query_embedding, chunk.embedding)
        if score > 0:
            scored.append((chunk.content, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def _rank_chunks(db: Session, query: str, top_k: int) -> list[tuple[KnowledgeChunk, float]]:
    """Rank knowledge chunks for a query, returning (chunk, score) pairs."""
    mode = get_settings().RAG_MODE or "hybrid"
    chunks = list(db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.id)))
    if not chunks:
        ingest(db)
        chunks = list(db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.id)))
    if not chunks:
        return []

    if mode == "vector":
        results = _vector_search(chunks, embed(query), top_k)
        scored = {c.content: (c, s) for c, s in results}
        return [scored[k] for k, _ in results]

    if mode == "bm25":
        index = _load_index(db)
        results = index.search(query, top_k=top_k)
        by_content = {c.content: c for c in chunks}
        return [(by_content[c], s) for c, s in results if c in by_content]

    # hybrid
    bm25 = dict(_load_index(db).search(query, top_k=top_k * 3))
    query_vec = embed(query)
    vector = dict(_vector_search(chunks, query_vec, top_k=top_k * 3))

    max_b = max(bm25.values()) if bm25 else 1.0
    max_v = max(vector.values()) if vector else 1.0
    keys = set(bm25) | set(vector)
    scored = [
        (content, 0.5 * (bm25.get(content, 0) / max_b) + 0.5 * (vector.get(content, 0) / max_v))
        for content in keys
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    by_content = {c.content: c for c in chunks}
    return [(by_content[c], s) for c, s in scored[:top_k] if c in by_content]


def search(db: Session, query: str, top_k: int = 3) -> list[tuple[str, float]]:
    """Return the top-k most relevant knowledge chunk contents."""
    return [(c.content, round(s, 4)) for c, s in _rank_chunks(db, query, top_k)]


def search_detailed(
    db: Session, query: str, top_k: int = 3
) -> list[dict]:
    """Return the top-k most relevant chunks with document metadata."""
    results: list[dict] = []
    for chunk, score in _rank_chunks(db, query, top_k):
        doc = db.get(KnowledgeDocument, chunk.document_id) if chunk.document_id else None
        results.append(
            {
                "content": chunk.content,
                "score": round(score, 4),
                "section": chunk.section,
                "document_id": doc.id if doc else None,
                "document_title": doc.title if doc else None,
                "source": doc.source if doc else None,
                "file_path": doc.file_path if doc else None,
            }
        )
    return results


def list_documents(db: Session) -> list[dict]:
    """Documents in the knowledge base with chunk counts."""
    counts = dict(
        db.execute(
            select(KnowledgeChunk.document_id, func.count(KnowledgeChunk.id))
            .group_by(KnowledgeChunk.document_id)
        ).all()
    )
    docs = list(db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.id)))
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "source": doc.source,
            "author": doc.author,
            "status": doc.status,
            "file_path": doc.file_path,
            "chunk_count": counts.get(doc.id, 0),
            "created_at": doc.created_at,
        }
        for doc in docs
    ]


def add_document(
    db: Session, filename: str, content: bytes, user_id: int
) -> tuple[bool, str]:
    """Persist an uploaded markdown document into the knowledge base.

    Writes the file under the knowledge directory (the trusted import source)
    and ingests it as a new document. Returns (ok, message).
    """
    if not filename.lower().endswith(".md") and not filename.lower().endswith(".txt"):
        return False, "Only .md or .txt knowledge documents are supported."
    text = content.decode("utf-8-sig", errors="replace")
    if len(text.strip()) < 100:
        return False, "The document is too short to be useful (min ~100 characters)."

    docs_dir = get_settings().knowledge_dir
    if not docs_dir.is_dir():
        docs_dir.mkdir(parents=True, exist_ok=True)

    safe = "".join(ch for ch in Path(filename).stem.lower() if ch.isalnum() or ch in "-_")[:80]
    safe = safe or "document"
    path = docs_dir / f"{safe}.md"
    path.write_text(text, encoding="utf-8")

    added = ingest(db)
    doc = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.file_path == str(path)))
    if added == 0 or doc is None:
        return False, "The document could not be ingested; it may already exist."
    doc.uploaded_by = user_id
    doc.source = doc.source or "User upload"
    db.commit()
    return True, doc.title


def delete_document(db: Session, document_id: int) -> bool:
    """Remove a document, its chunks and its source file from the knowledge base."""
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None:
        return False
    chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)))
    for chunk in chunks:
        db.delete(chunk)
    db.delete(doc)
    db.commit()
    if doc.file_path:
        try:
            path = Path(doc.file_path)
            if path.is_file() and path.parent == get_settings().knowledge_dir:
                path.unlink()
        except OSError:
            logger.warning("could not remove knowledge file %s", doc.file_path)
    return True


def chunk_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0)


def indexed_count(db: Session) -> int:
    """Number of chunks that already have an embedding."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(KnowledgeChunk.embedding.is_not(None))
        )
        or 0
    )


def available() -> bool:
    return get_settings().knowledge_dir.is_dir()