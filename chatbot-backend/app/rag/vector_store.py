from typing import List

import chromadb

from app.config.settings import settings

_client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
_collection = _client.get_or_create_collection(name="documents")


def add_chunks(
    document_id: int,
    filename: str,
    chunks: List[str],
    embeddings: List[List[float]],
    start_index: int = 0,
    page_numbers: List[int] | None = None,
) -> None:
    if not chunks:
        return

    ids = [f"doc{document_id}_chunk{start_index + i}" for i in range(len(chunks))]
    metadatas = []
    for i in range(len(chunks)):
        meta = {"document_id": document_id, "filename": filename, "chunk_index": start_index + i}
        if page_numbers is not None:
            meta["page_number"] = page_numbers[i]
        metadatas.append(meta)

    _collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )


def delete_document_chunks(document_id: int) -> None:
    _collection.delete(where={"document_id": document_id})


def reset_collection() -> None:
    """Drops and recreates the collection - use when switching embedding
    models, since Chroma locks a collection's vector dimension on first
    insert and mixing dimensions causes InvalidArgumentError."""
    global _collection
    _client.delete_collection(name="documents")
    _collection = _client.get_or_create_collection(name="documents")


def query(query_embedding: List[float], top_k: int = 5, where: dict | None = None) -> dict:
    kwargs = {"query_embeddings": [query_embedding], "n_results": top_k}
    if where:
        kwargs["where"] = where
    return _collection.query(**kwargs)