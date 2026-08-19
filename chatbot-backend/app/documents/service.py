import hashlib
import uuid
from pathlib import Path
from typing import Optional, Tuple

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.document import Document
from app.utils.text_extraction import extract_text


def validate_file(file: UploadFile) -> str:
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
        )
    return ext


def compute_content_hash(file_bytes: bytes) -> str:
    """Hash of the raw file bytes - identity is based on CONTENT, not filename."""
    return hashlib.sha256(file_bytes).hexdigest()


def find_duplicate(db: Session, content_hash: str) -> Optional[Document]:
    return db.query(Document).filter(Document.content_hash == content_hash).first()


def save_upload_file(filename: str, file_bytes: bytes) -> Tuple[str, int]:
    upload_dir = Path(settings.UPLOAD_FOLDER)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # uuid prefix avoids filesystem name collisions (separate concern from
    # content dedup, which is handled via content_hash before this is called)
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    dest_path = upload_dir / safe_name

    with dest_path.open("wb") as buffer:
        buffer.write(file_bytes)

    return str(dest_path), len(file_bytes)


def create_document_record(
    db: Session,
    filename: str,
    filepath: str,
    content_type: str,
    file_size: int,
    content_hash: str,
    uploaded_by_erp_id: Optional[int] = None,
) -> Document:
    document = Document(
        filename=filename,
        filepath=filepath,
        content_type=content_type,
        file_size=file_size,
        content_hash=content_hash,
        uploaded_by_erp_id=uploaded_by_erp_id,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def remove_stored_file(document: Document) -> bool:
    """Delete the uploaded file an untrained document points at.

    Without this the file survives in `uploads/`, and the next
    `python -m app.cli reindex` would train it straight back in - an
    administrator who removed a superseded policy would find it answering
    questions again after the next deployment.

    Only files inside the upload folder are touched, so a path that somehow
    points elsewhere is left alone rather than deleted.
    """
    if not document.filepath:
        return False

    target = Path(document.filepath).resolve()
    folder = Path(settings.UPLOAD_FOLDER).resolve()

    if folder not in target.parents:
        return False

    try:
        target.unlink(missing_ok=True)
        return True
    except OSError:
        # A locked file must not turn an untrain into a 500; the row and the
        # vectors are already gone, which is what makes it stop answering.
        return False


def process_document(db: Session, document: Document) -> Document:
    """Extracts and cleans text, then updates the document's status."""
    document.status = "extracting"
    db.commit()

    try:
        text = extract_text(document.filepath, document.content_type)
        document.extracted_text = text
        document.status = "ready"
    except Exception:
        document.status = "failed"
        document.extracted_text = None
        db.commit()
        raise
    else:
        db.commit()
        db.refresh(document)

    return document