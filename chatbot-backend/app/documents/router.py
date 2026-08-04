from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

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

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _run_pipeline(document_id: int) -> None:
    """
    Runs extraction -> chunking -> embedding -> storage in the background.
    Opens its OWN db session since the request-scoped one from get_db()
    is already closed by the time this runs.

    IMPORTANT: exceptions here do NOT reach the API caller - this is a
    background task. Check the uvicorn console/terminal for tracebacks,
    or the document's status will simply show "failed".
    """
    print(f">>> _run_pipeline STARTED for document {document_id}", flush=True)
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            print(f">>> _run_pipeline: document {document_id} NOT FOUND in DB", flush=True)
            logger.error("Background pipeline: document %s not found", document_id)
            return

        print(f">>> _run_pipeline: found document {document_id}, status={document.status}", flush=True)

        try:
            print(f">>> _run_pipeline: calling process_document (extraction)...", flush=True)
            document = service.process_document(db, document)
            print(f">>> _run_pipeline: extraction done, status={document.status}, "
                  f"text_len={len(document.extracted_text or '')}", flush=True)

            print(f">>> _run_pipeline: calling index_document (chunk/embed/store)...", flush=True)
            index_document(db, document)
            print(f">>> _run_pipeline: index_document finished, status={document.status}, "
                  f"total_chunks={document.total_chunks}, processed_chunks={document.processed_chunks}",
                  flush=True)
        except Exception as exc:
            print(f">>> _run_pipeline: EXCEPTION: {type(exc).__name__}: {exc}", flush=True)
            import traceback
            traceback.print_exc()
            logger.exception("Background pipeline failed for document %s", document_id)
            db.rollback()
            document.status = "failed"
            db.commit()
    finally:
        db.close()
        print(f">>> _run_pipeline FINISHED for document {document_id}", flush=True)


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # 1. validate extension
    try:
        service.validate_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 2. read bytes once, hash them - dedup is by CONTENT, not filename
    file_bytes = await file.read()
    content_hash = service.compute_content_hash(file_bytes)

    existing = service.find_duplicate(db, content_hash)
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A document with identical content already exists.",
                "existing_document_id": existing.id,
                "existing_filename": existing.filename,
            },
        )

    # 3. save to disk (only reached if content is new)
    filepath, file_size = service.save_upload_file(file.filename, file_bytes)

    # 4. create metadata record (status="uploaded")
    document = service.create_document_record(
        db=db,
        filename=file.filename,
        filepath=filepath,
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        content_hash=content_hash,
    )

    # 5. kick off extract -> chunk -> embed -> store in the background.
    # The request returns immediately; poll GET /documents/{id}/status
    # for live progress instead of waiting on this call.
    print(f">>> upload_document: scheduling background task for document {document.id}", flush=True)
    background_tasks.add_task(_run_pipeline, document.id)

    return document


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    total = document.total_chunks or 0
    processed = document.processed_chunks or 0

    if total > 0:
        percent = round((processed / total) * 100, 1)
    else:
        # no chunk count yet (still extracting) unless it's already finished
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
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_document_chunks(document_id)
    db.delete(document)
    db.commit()
    return {"detail": "Document deleted"}