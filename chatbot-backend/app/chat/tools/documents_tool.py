import logging
from typing import Any, Dict, List

from app.rag.retriever import retrieve_top_chunks

logger = logging.getLogger(__name__)


async def search_documents(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Searches HR policy documents/SOPs via the existing RAG pipeline."""
    logger.info("search_documents: query=%r top_k=%d", query, top_k)

    chunks = retrieve_top_chunks(query, top_k=top_k)

    distances = [c.get("distance") for c in chunks]
    logger.info("search_documents: query=%r retrieved %d chunk(s), distances=%s",
                query, len(chunks), distances)

    if not chunks:
        logger.warning("search_documents: query=%r returned 0 chunks - check that "
                        "documents are actually indexed (status=indexed) for this collection", query)

    return chunks