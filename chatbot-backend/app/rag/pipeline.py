import logging

from sqlalchemy.orm import Session

from app.models.document import Document
from app.rag.chunker import chunk_text
from app.rag.embeddings import embed_passages
from app.rag.vector_store import add_chunks

logger = logging.getLogger(__name__)


def index_document(db: Session, document: Document) -> Document:
    if not document.extracted_text:
        document.status = "failed"
        db.commit()
        db.refresh(document)
        logger.warning("Document %s: no extracted text, skipping indexing", document.id)
        return document

    chunks_with_pages = chunk_text(document.extracted_text)
    if not chunks_with_pages:
        document.status = "failed"
        db.commit()
        db.refresh(document)
        logger.warning("Document %s: produced 0 chunks, skipping indexing", document.id)
        return document

    try:
        document.total_chunks = len(chunks_with_pages)
        document.processed_chunks = 0
        document.status = "embedding"
        db.commit()
        logger.info("Document %s: embedding %s chunks", document.id, len(chunks_with_pages))

        for i, (page_number, chunk) in enumerate(chunks_with_pages):
            embedding = embed_passages([chunk])[0]
            add_chunks(
                document.id, document.filename, [chunk], [embedding],
                start_index=i, page_numbers=[page_number],
            )

            document.processed_chunks = i + 1
            db.commit()

        document.status = "indexed"
        db.commit()
        db.refresh(document)

    except Exception:
        logger.exception("Document %s: indexing failed", document.id)
        db.rollback()
        document.status = "failed"
        db.commit()
        db.refresh(document)
        raise

    return document