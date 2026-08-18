"""Finding the passages an answer should be built from."""

import logging
from typing import Dict, List, Optional

from app.config.settings import settings
from app.rag.embeddings import embed_query
from app.rag.vector_store import query as vector_query

logger = logging.getLogger(__name__)


def retrieve_top_chunks(
    question: str,
    top_k: Optional[int] = None,
    document_id: Optional[int] = None,
    max_distance: Optional[float] = None,
) -> List[Dict]:
    """The most relevant stored passages, closest first.

    `document_id` scopes the search to one trained document; omit it to search
    everything indexed. Anything past `max_distance` is dropped: a vector store
    always returns its nearest neighbours, even when the nearest thing it has is
    unrelated, and passing that to the model is how a chatbot ends up quoting
    the holiday schedule at somebody asking about probation.
    """
    top_k = top_k or settings.RETRIEVAL_TOP_K
    ceiling = settings.RETRIEVAL_MAX_DISTANCE if max_distance is None else max_distance

    query_embedding = embed_query(question)
    where_filter = {"document_id": document_id} if document_id is not None else None
    results = vector_query(query_embedding, top_k=top_k, where=where_filter)

    documents = results.get("documents") or [[]]
    documents = documents[0] if documents else []
    metadatas = (results.get("metadatas") or [[]])[0] if results.get("metadatas") else []
    distances = (results.get("distances") or [[]])[0] if results.get("distances") else []

    if not distances:
        distances = [None] * len(documents)

    chunks: List[Dict] = []
    dropped = 0
    for text, meta, distance in zip(documents, metadatas, distances):
        meta = meta or {}
        if distance is not None and ceiling is not None and distance > ceiling:
            dropped += 1
            continue

        chunks.append(
            {
                "text": text,
                "filename": meta.get("filename"),
                "document_id": meta.get("document_id"),
                "chunk_index": meta.get("chunk_index"),
                "page_number": meta.get("page_number"),
                "distance": distance,
            }
        )

    logger.info(
        "retrieve_top_chunks: question=%r kept=%d dropped=%d (ceiling=%s) document_id=%s",
        question[:80], len(chunks), dropped, ceiling, document_id,
    )

    return chunks
