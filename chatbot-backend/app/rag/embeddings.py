"""Embedding text with the local Ollama model.

nomic-embed-text is trained with task prefixes, and they are not decoration:
embedding a passage as though it were a query measurably degrades retrieval.
Storing and searching therefore go through different functions, so the right
prefix is impossible to forget at a call site.
"""

import logging
from typing import List

import ollama

from app.config.settings import settings

logger = logging.getLogger(__name__)

_client = ollama.Client(host=settings.OLLAMA_BASE_URL)

_PASSAGE_PREFIX = "search_document: "
_QUERY_PREFIX = "search_query: "

# Ollama embeds a list in one request; batching turns indexing a manual from
# hundreds of round trips into a few dozen.
_BATCH_SIZE = 16


def _embed_many(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []

    try:
        response = _client.embed(model=settings.EMBEDDING_MODEL, input=texts)
        return list(response["embeddings"])
    except (AttributeError, KeyError, TypeError):
        # Older ollama clients only have the single-prompt endpoint.
        logger.info("_embed_many: batch endpoint unavailable, embedding one at a time")
        return [
            _client.embeddings(model=settings.EMBEDDING_MODEL, prompt=text)["embedding"]
            for text in texts
        ]


def embed_passages(texts: List[str]) -> List[List[float]]:
    """Embed document chunks for storage."""
    prefixed = [f"{_PASSAGE_PREFIX}{text}" for text in texts]

    vectors: List[List[float]] = []
    for start in range(0, len(prefixed), _BATCH_SIZE):
        vectors.extend(_embed_many(prefixed[start:start + _BATCH_SIZE]))

    return vectors


def embed_query(text: str) -> List[float]:
    """Embed a question for searching."""
    return _embed_many([f"{_QUERY_PREFIX}{text}"])[0]
