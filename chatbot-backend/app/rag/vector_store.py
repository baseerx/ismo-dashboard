"""The Chroma collection holding the trained document chunks.

The collection is created with cosine distance rather than Chroma's default
squared-L2. With unnormalised embeddings, L2 distances land in the hundreds and
the gap between "relevant" and "unrelated" moves with document length, so no
fixed relevance threshold holds. Cosine distance is bounded (0 = identical,
1 = unrelated, 2 = opposite), which makes `RETRIEVAL_MAX_DISTANCE` meaningful.

Changing the space is a property of the collection, not of a query: a store
built under the old setting has to be rebuilt, which `python -m app.cli
reindex` does from the files in `uploads/`.
"""

import logging
from typing import Dict, List, Optional

import chromadb

from app.config.settings import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents"
DISTANCE_SPACE = "cosine"

_client = chromadb.PersistentClient(path=settings.CHROMA_PATH)


def _open_collection():
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": DISTANCE_SPACE},
    )


_collection = _open_collection()

# Chunks this process knows about. Chroma shares its metadata between
# processes but not the in-memory vector index: a document added by another
# process (`python -m app.cli ingest` while the service is running) raises the
# count here yet is never returned by a search until the service restarts.
# Tracking the number we wrote ourselves is what lets `index_is_stale` notice.
_known_chunks = _collection.count()


def _remember_size() -> None:
    global _known_chunks
    _known_chunks = _collection.count()


def index_is_stale() -> bool:
    """True when another process has written to the store since startup.

    Those documents are invisible to search in this process, so the honest
    thing is to report it rather than quietly answer without them.
    """
    try:
        return _collection.count() != _known_chunks
    except Exception:
        return False


def collection_info() -> Dict:
    return {
        "name": COLLECTION_NAME,
        "chunks": _collection.count(),
        "space": (_collection.metadata or {}).get("hnsw:space", "unknown"),
        "path": settings.CHROMA_PATH,
        "searchable_chunks": _known_chunks,
        "stale": index_is_stale(),
    }


def uses_cosine() -> bool:
    """False for a store built before the switch, which needs a reindex."""
    return (_collection.metadata or {}).get("hnsw:space") == DISTANCE_SPACE


def add_chunks(
    document_id: int,
    filename: str,
    chunks: List[str],
    embeddings: List[List[float]],
    start_index: int = 0,
    page_numbers: Optional[List[int]] = None,
) -> None:
    if not chunks:
        return

    ids = [f"doc{document_id}_chunk{start_index + i}" for i in range(len(chunks))]
    metadatas = []
    for i in range(len(chunks)):
        meta = {
            "document_id": document_id,
            "filename": filename,
            "chunk_index": start_index + i,
        }
        if page_numbers is not None:
            meta["page_number"] = page_numbers[i]
        metadatas.append(meta)

    _collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    _remember_size()


def delete_document_chunks(document_id: int) -> None:
    _collection.delete(where={"document_id": document_id})
    _remember_size()


def reset_collection() -> None:
    """Drop and recreate the collection.

    Needed when the embedding model changes (Chroma fixes a collection's vector
    dimension on first insert) or when the distance space changes.
    """
    global _collection
    try:
        _client.delete_collection(name=COLLECTION_NAME)
    except Exception:  # nothing to delete on a fresh store
        logger.info("reset_collection: no existing collection to drop")
    _collection = _open_collection()
    _remember_size()
    logger.info("reset_collection: collection recreated with %s distance", DISTANCE_SPACE)


def query(query_embedding: List[float], top_k: int = 5, where: Optional[dict] = None) -> dict:
    kwargs = {"query_embeddings": [query_embedding], "n_results": top_k}
    if where:
        kwargs["where"] = where
    return _collection.query(**kwargs)
