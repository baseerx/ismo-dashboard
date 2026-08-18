from typing import Dict, List, Optional

from app.rag.embeddings import embed_query
from app.rag.vector_store import query as vector_query


def retrieve_top_chunks(
    question: str, top_k: int = 5, document_id: Optional[int] = None
) -> List[Dict]:
    """
    Embeds the user's question (with the e5 "query: " prefix, handled
    inside embed_query) and searches Chroma for the most relevant stored
    chunks. Pass document_id to scope the search to a single document;
    omit it to search across everything indexed ("General" mode).

    Returns a list of dicts ordered by relevance (closest first):
        {"text", "filename", "document_id", "chunk_index", "distance"}
    """
    query_embedding = embed_query(question)
    where_filter = {"document_id": document_id} if document_id is not None else None
    results = vector_query(query_embedding, top_k=top_k, where=where_filter)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0] if results.get("distances") else [None] * len(documents)

    chunks = []
    for text, meta, distance in zip(documents, metadatas, distances):
        chunks.append({
            "text": text,
            "filename": meta.get("filename"),
            "document_id": meta.get("document_id"),
            "chunk_index": meta.get("chunk_index"),
            "distance": distance,
        })

    return chunks