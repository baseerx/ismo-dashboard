"""FastAPI entry point for the HR assistant.

Run it with:  uvicorn app.main:app --host 0.0.0.0 --port 8000
or, on a Windows host:  run_server.bat
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.identity import Identity, current_identity
from app.chat.router import router as chat_router
from app.config.settings import settings
from app.database.db import Base, engine
from app.database.schema import ensure_schema
from app.documents.router import router as documents_router
from app.models import chat, document  # noqa: F401  # registers the tables
from app.rag.vector_store import collection_info, uses_cosine
from app.reports.router import router as reports_router

# A Windows console defaults to cp1252, and one non-Latin character in a
# question would otherwise take down the log handler mid-request.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("app")

# Creates the chatbot's own three tables if they are missing, then adds any
# column an older deployment of them predates.
Base.metadata.create_all(bind=engine)
ensure_schema()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Says on startup what this instance is actually wired to.

    Most support questions about this service ("why does it not know the
    policy", "why is everything 401") are answered by these three lines.
    """
    store = collection_info()
    logger.info(
        "HR assistant ready | db=%s@%s | model=%s | embeddings=%s | %s chunks (%s)",
        settings.DB_NAME, settings.DB_HOST, settings.MODEL_NAME,
        settings.EMBEDDING_MODEL, store["chunks"], store["space"],
    )
    if not uses_cosine():
        logger.warning(
            "The vector store was built with %s distance, not cosine. Relevance "
            "filtering will misbehave until you run: python -m app.cli reindex --reset",
            store["space"],
        )
    if not store["chunks"]:
        logger.warning(
            "No document chunks are indexed - policy questions will have nothing to "
            "answer from. An administrator can upload a document from the chat widget, "
            "or run: python -m app.cli reindex"
        )

    yield


app = FastAPI(
    lifespan=lifespan,
    title="ISMO HR Assistant",
    description=(
        "Retrieval-augmented answers from the HR policy manual, plus each employee's "
        "own leave and attendance records, scoped by the dashboard's own login token."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # So the widget can read the filename off a report download.
    expose_headers=["Content-Disposition"],
)

app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(reports_router)


@app.get("/")
def root():
    """Unauthenticated health check, for the service wrapper and load balancer."""
    store = collection_info()
    return {
        "status": "ok",
        "service": "ismo-hr-assistant",
        "model": settings.MODEL_NAME,
        "indexed_chunks": store["chunks"],
    }


@app.get("/me")
def me(identity: Identity = Depends(current_identity)):
    """Who the service thinks you are — useful when a token looks wrong."""
    return {
        "erp_id": identity.erp_id,
        "name": identity.name,
        "section": identity.section_name,
        "is_admin": identity.is_admin,
    }
