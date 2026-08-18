"""Chunk -> embed -> store, with progress the upload UI can poll."""

import logging

from sqlalchemy.orm import Session

from app.models.document import Document
from app.rag.chunker import chunk_text
from app.rag.embeddings import embed_passages
from app.rag.vector_store import add_chunks, delete_document_chunks

logger = logging.getLogger(__name__)

# Chunks per embedding round. Small enough that the progress bar moves often,
# large enough to keep the number of Ollama round trips down.
BATCH_SIZE = 16


def index_document(db: Session, document: Document) -> Document:
    if not document.extracted_text:
        document.status = "failed"
        db.commit()
        db.refresh(document)
        logger.warning("Document %s: no extracted text, nothing to index", document.id)
        return document

    chunks_with_pages = chunk_text(document.extracted_text)
    if not chunks_with_pages:
        document.status = "failed"
        db.commit()
        db.refresh(document)
        logger.warning("Document %s: produced 0 chunks", document.id)
        return document

    try:
        document.total_chunks = len(chunks_with_pages)
        document.processed_chunks = 0
        document.status = "embedding"
        db.commit()
        logger.info("Document %s: embedding %d chunks", document.id, len(chunks_with_pages))

        # Re-indexing an existing document would otherwise leave the previous
        # run's chunks behind when the new one produces fewer of them.
        delete_document_chunks(document.id)

        for start in range(0, len(chunks_with_pages), BATCH_SIZE):
            batch = chunks_with_pages[start:start + BATCH_SIZE]
            pages = [page for page, _ in batch]
            texts = [text for _, text in batch]

            embeddings = embed_passages(texts)
            add_chunks(
                document.id,
                document.filename,
                texts,
                embeddings,
                start_index=start,
                page_numbers=pages,
            )

            document.processed_chunks = start + len(batch)
            db.commit()

        document.status = "indexed"
        db.commit()
        db.refresh(document)
        logger.info("Document %s: indexed %d chunks", document.id, document.total_chunks)

    except Exception:
        logger.exception("Document %s: indexing failed", document.id)
        db.rollback()
        document.status = "failed"
        db.commit()
        db.refresh(document)
        raise

    return document
