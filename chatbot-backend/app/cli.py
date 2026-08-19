"""Command line side of document training.

Two things need doing outside the browser. A fresh deployment starts with an
empty vector store, and the store has to be rebuilt whenever the embedding
model or the distance space changes. Both are this module:

    python -m app.cli status                 what is indexed right now
    python -m app.cli ingest <file...>       train specific files
    python -m app.cli reindex                rebuild from everything in uploads/
    python -m app.cli reindex --reset        ...after dropping the collection

The vector store is deliberately not kept in version control - it is derived
data, it is large, and a binary file that changes on every upload is a
guaranteed merge conflict. The source documents in `uploads/` are what is
tracked, and this rebuilds the index from them.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from app.config.settings import settings
from app.database.db import Base, SessionLocal, engine
from app.documents import service
from app.models import chat, document as document_model  # noqa: F401  (register tables)
from app.models.document import Document
from app.rag.pipeline import index_document
from app.rag.vector_store import collection_info, reset_collection

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("app.cli")


def _ingest_path(db, path: Path) -> bool:
    if not path.exists():
        print(f"  ! {path} does not exist")
        return False

    if path.suffix.lower() not in settings.ALLOWED_EXTENSIONS:
        print(f"  ! {path.name}: unsupported type {path.suffix}")
        return False

    payload = path.read_bytes()
    content_hash = service.compute_content_hash(payload)

    existing = service.find_duplicate(db, content_hash)
    if existing:
        record = existing
        print(f"  = {path.name}: already registered as document {record.id}, re-indexing")
    else:
        if path.resolve().parent == Path(settings.UPLOAD_FOLDER).resolve():
            # Already in the upload folder - registering it in place, rather
            # than copying, keeps `reindex` from leaving a second copy of every
            # document behind on a fresh database.
            stored_path, size = str(path), len(payload)
        else:
            stored_path, size = service.save_upload_file(path.name, payload)
        record = service.create_document_record(
            db=db,
            filename=path.name,
            filepath=stored_path,
            content_type="application/pdf" if path.suffix.lower() == ".pdf" else "text/plain",
            file_size=size,
            content_hash=content_hash,
        )
        print(f"  + {path.name}: registered as document {record.id}")

    record = service.process_document(db, record)
    index_document(db, record)
    print(f"  > {path.name}: {record.status}, {record.total_chunks} chunk(s)")
    return record.status == "indexed"


def command_status() -> int:
    info = collection_info()
    print(f"vector store : {info['path']}")
    print(f"collection   : {info['name']} ({info['space']} distance)")
    print(f"chunks       : {info['chunks']}")

    db = SessionLocal()
    try:
        documents = db.query(Document).order_by(Document.created_at.desc()).all()
        print(f"database     : {settings.DB_NAME} on {settings.DB_HOST}")
        print(f"documents    : {len(documents)}")
        for record in documents:
            print(
                f"  [{record.id}] {record.filename} — {record.status}, "
                f"{record.processed_chunks or 0}/{record.total_chunks or 0} chunks"
            )
    finally:
        db.close()

    return 0


def command_ingest(paths: List[str]) -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    failures = 0
    try:
        for raw in paths:
            print(f"- {raw}")
            if not _ingest_path(db, Path(raw)):
                failures += 1
    finally:
        db.close()

    return 1 if failures else 0


def command_reindex(reset: bool) -> int:
    Base.metadata.create_all(bind=engine)

    if reset:
        print("dropping the existing collection")
        reset_collection()

    folder = Path(settings.UPLOAD_FOLDER)
    files = sorted(
        path for path in folder.glob("*")
        if path.is_file() and path.suffix.lower() in settings.ALLOWED_EXTENSIONS
    )

    if not files:
        print(f"nothing to index: {folder.resolve()} has no supported documents")
        return 1

    print(f"re-indexing {len(files)} file(s) from {folder.resolve()}")
    result = command_ingest([str(path) for path in files])
    _restart_notice()
    return result


def _restart_notice() -> None:
    """Chroma shares its metadata between processes but not its search index.

    A running service therefore keeps answering from the documents it loaded at
    startup, and silently omits anything trained here until it is restarted.
    """
    print()
    print("NOTE: if the assistant service is running, restart it now -")
    print("      documents trained from the command line are not searchable")
    print("      by a process that started before them.")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="Document training utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="show what is indexed")

    ingest = subparsers.add_parser("ingest", help="train one or more files")
    ingest.add_argument("paths", nargs="+")

    reindex = subparsers.add_parser("reindex", help="rebuild the index from uploads/")
    reindex.add_argument(
        "--reset",
        action="store_true",
        help="drop the collection first (needed after changing embedding model or distance space)",
    )

    args = parser.parse_args(argv)

    if args.command == "status":
        return command_status()
    if args.command == "ingest":
        result = command_ingest(args.paths)
        _restart_notice()
        return result
    if args.command == "reindex":
        return command_reindex(args.reset)

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
