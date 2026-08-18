import logging
from typing import Any, Dict, List, Optional

from app.rag.retriever import retrieve_top_chunks

logger = logging.getLogger(__name__)


async def search_documents(
    query: str, top_k: Optional[int] = None, document_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Search the trained HR documents.

    Returns [] when nothing is close enough to be relevant, which the caller
    must treat as "not in the documents" rather than filling the gap from the
    model's own knowledge of HR practice elsewhere.
    """
    if not (query or "").strip():
        return []

    chunks = retrieve_top_chunks(query, top_k=top_k, document_id=document_id)

    if not chunks:
        logger.info("search_documents: nothing relevant for %r", query[:80])

    return chunks
