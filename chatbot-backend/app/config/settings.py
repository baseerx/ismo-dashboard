"""Runtime configuration.

Everything is env-overridable so the same tree runs on a developer machine,
staging and production. The defaults describe the ISMO development
environment, which keeps `uvicorn app.main:app` working with no .env file.
"""

import os
from pathlib import Path
from typing import List
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _csv(name: str, default: str) -> List[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # ==========================
    # Ollama (local models)
    # ==========================
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    MODEL_NAME = os.getenv("MODEL_NAME", "mistral:latest")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    # Answers are grounded in retrieved text, so a low temperature is wanted:
    # this assistant quotes policy and reports attendance, it does not riff.
    MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.1"))
    MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "700"))

    # ==========================
    # SQL Server — the same database the Django dashboard uses.
    # HR data (employees / leaves / attendance) is read from here, and the
    # chatbot's own tables (conversations, messages, documents) live here too.
    # ==========================
    DB_HOST = os.getenv("DB_HOST", "192.168.157.51")
    DB_PORT = os.getenv("DB_PORT", "9090")
    DB_USER = os.getenv("DB_USER", "sa")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Sa@157")
    DB_NAME = os.getenv("DB_NAME", "Attendance_System")
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    DB_ENCRYPT = os.getenv("DB_ENCRYPT", "no")
    DB_TRUST_SERVER_CERTIFICATE = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")

    # ==========================
    # Identity
    # ==========================
    # The dashboard's login endpoint hands the browser a JWT signed with
    # Django's SECRET_KEY. This service verifies that signature instead of
    # trusting anything the browser says about who it is, which is what keeps
    # one employee from reading another's leave or attendance record.
    DJANGO_SECRET_KEY = os.getenv(
        "DJANGO_SECRET_KEY",
        "django-insecure-4&quhz))qhg9a(t#^fmycf=bf=dn#5n$k1k2d61)u+d&=ro8e#",
    )
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    # Tolerance for clock skew between the Django host and this one.
    JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", "60"))

    # ==========================
    # HTTP
    # ==========================
    # 5174 is included because Vite silently falls back to it when 5173 is
    # already taken by another project on the same machine, and a widget that
    # cannot reach the service looks broken rather than misconfigured.
    CORS_ORIGINS = _csv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://192.168.157.55:9000,http://192.168.157.55:9002",
    )

    # ==========================
    # Storage
    # ==========================
    CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "25"))

    # ==========================
    # Retrieval
    # ==========================
    RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "6"))
    # Chroma returns cosine distance; anything past this is noise rather than
    # a weak match, and answering from it produces confident nonsense.
    RETRIEVAL_MAX_DISTANCE = float(os.getenv("RETRIEVAL_MAX_DISTANCE", "0.62"))

    # ==========================
    # Reports
    # ==========================
    REPORT_MAX_ROWS = int(os.getenv("REPORT_MAX_ROWS", "5000"))
    REPORT_MAX_RANGE_DAYS = int(os.getenv("REPORT_MAX_RANGE_DAYS", "800"))

    # The assistant never writes HR data - that is enforced in
    # app/database/guard.py, not merely intended. What it does write is its own
    # chat log, which is what makes follow-up questions and the "past chats"
    # panel work. Set this false for a service that writes nothing at all
    # during a conversation; answers are unchanged, but each question is then
    # answered on its own with no memory of the last one.
    PERSIST_CHAT_HISTORY = _flag("PERSIST_CHAT_HISTORY", "true")

    DEBUG_SQL = _flag("DEBUG_SQL")

    def __init__(self):
        Path(self.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
        Path(self.CHROMA_PATH).mkdir(parents=True, exist_ok=True)

    @property
    def DATABASE_URL(self) -> str:
        # SQL Server expects "host,port" (comma, not colon). Named instances
        # such as HOST\SQLEXPRESS are resolved by the browser service, so a
        # port is only appended when one is configured.
        server = f"{self.DB_HOST},{self.DB_PORT}" if self.DB_PORT else self.DB_HOST

        conn_str = (
            f"DRIVER={{{self.DB_DRIVER}}};"
            f"SERVER={server};"
            f"DATABASE={self.DB_NAME};"
            f"UID={self.DB_USER};"
            f"PWD={self.DB_PASSWORD};"
            f"Encrypt={self.DB_ENCRYPT};"
            f"TrustServerCertificate={self.DB_TRUST_SERVER_CERTIFICATE};"
        )

        return "mssql+pyodbc:///?odbc_connect=" + quote_plus(conn_str)


settings = Settings()
