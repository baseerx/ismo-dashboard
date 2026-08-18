
from typing import List

import ollama

from app.config.settings import settings

_client = ollama.Client(host=settings.OLLAMA_BASE_URL)

# intfloat/e5-* models are trained with instruction prefixes - queries and
# passages MUST be prefixed differently or retrieval quality drops sharply.
_PASSAGE_PREFIX = "passage: "
_QUERY_PREFIX = "query: "


def _to_list(vector) -> List[float]:
    return vector.tolist() if hasattr(vector, "tolist") else vector

# nomic-embed-text is trained with instruction prefixes - queries and
# passages MUST be prefixed differently or retrieval quality drops sharply.
# NOTE: these prefixes are specific to nomic-embed-text, NOT the same as
# the "query: " / "passage: " prefixes the previous e5 model used.
_PASSAGE_PREFIX = "search_document: "
_QUERY_PREFIX = "search_query: "


def embed_passages(texts: List[str]) -> List[List[float]]:
    """Embed document chunks before storing them in the vector DB."""
    return [
        _client.embeddings(
            model=settings.EMBEDDING_MODEL,
            prompt=f"{_PASSAGE_PREFIX}{text}",
        )["embedding"]
        for text in texts
    ]


def embed_query(text: str) -> List[float]:
    """Embed a user's question before searching the vector DB."""
    result = _client.embeddings(
        model=settings.EMBEDDING_MODEL,
        prompt=f"{_QUERY_PREFIX}{text}",
    )
    return result["embedding"]