"""Training documents into the assistant.

Uploading is administrator-only: a trained document is answered from for every
employee in the organisation, so it is a publishing action, not a personal one.
Listing is open to any signed-in employee, because the widget shows which
documents it can search and cites them in its answers.
"""

import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth.identity import Identity, current_identity, require_admin
from app.config.settings import settings
from app.database.db import SessionLocal, get_db
from app.documents import service
from app.documents.schemas import (
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
)
from app.models.document import Document
from app.rag.pipeline import index_document
from app.rag.vector_store import delete_document_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _run_pipeline(document_id: int) -> None:
    """Extract -> chunk -> embed -> store, after the upload response is sent.

    Opens its own session: the request-scoped one from `get_db` is closed by the
    time this runs. Nothing raised here can reach the caller, which is why the
    document's `status` is the contract - the widget polls
    GET /documents/{id}/status and shows "failed" if this gives up.
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error("training: document %s vanished before indexing", document_id)
            return

        try:
            document = service.process_document(db, document)
            index_document(db, document)
            logger.info(
                "training: document %s finished as %s (%s chunks)",
                document_id, document.status, document.total_chunks,
            )
        except Exception:
            logger.exception("training: document %s failed", document_id)
            db.rollback()
            document.status = "failed"
            db.commit()
    finally:
        db.close()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_admin),
):
    try:
        service.validate_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Read once, then judge identity by content: the same manual uploaded under
    # a new filename is the same manual, and indexing it twice would double
    # every passage in the retrieval results.
    file_bytes = await file.read()

    limit = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"That file is larger than the {settings.MAX_FILE_SIZE_MB} MB limit.",
        )
    if not file_bytes:
        raise HTTPException(status_code=400, detail="That file is empty.")

    content_hash = service.compute_content_hash(file_bytes)

    existing = service.find_duplicate(db, content_hash)
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f'"{existing.filename}" already contains exactly this content.',
                "existing_document_id": existing.id,
                "existing_filename": existing.filename,
            },
        )

    filepath, file_size = service.save_upload_file(file.filename, file_bytes)

    document = service.create_document_record(
        db=db,
        filename=file.filename,
        filepath=filepath,
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        content_hash=content_hash,
        uploaded_by_erp_id=identity.erp_id,
    )

    logger.info(
        "training: document %s (%s) queued by erp=%s", document.id, file.filename, identity.erp_id
    )
    background_tasks.add_task(_run_pipeline, document.id)

    return document


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(current_identity),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    total = document.total_chunks or 0
    processed = document.processed_chunks or 0

    if total > 0:
        percent = round((processed / total) * 100, 1)
    else:
        # No chunk count yet means extraction is still running, unless the whole
        # thing already finished.
        percent = 100.0 if document.status == "indexed" else 0.0

    return DocumentStatusResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        total_chunks=total,
        processed_chunks=processed,
        progress_percent=percent,
    )


@router.get("/", response_model=List[DocumentListResponse])
def list_documents(
    db: Session = Depends(get_db),
    identity: Identity = Depends(current_identity),
):
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(current_identity),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_admin),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Chunks first: a document row without its vectors is recoverable, whereas
    # orphaned vectors would keep being cited with no document to point at.
    delete_document_chunks(document_id)
    removed = service.remove_stored_file(document)
    db.delete(document)
    db.commit()

    logger.info(
        "training: document %s deleted by erp=%s (file removed: %s)",
        document_id, identity.erp_id, removed,
    )
    return {"detail": "Document deleted"}
