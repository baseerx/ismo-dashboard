import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ==========================
    # Ollama (local)
    # ==========================
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "ollama")
    MODEL_NAME = os.getenv("MODEL_NAME", "mistral:latest")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    # ==========================
    # SQL Server
    # ==========================
    DB_HOST = os.getenv("DB_HOST", "192.168.157.51")
    DB_PORT = os.getenv("DB_PORT", "9090")
    DB_USER = os.getenv("DB_USER", "sa")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Sa@157")
    DB_NAME = os.getenv("DB_NAME", "Attendance_Stage")
    DB_DRIVER = os.getenv(
        "DB_DRIVER",
        "ODBC Driver 17 for SQL Server",
    )

    DB_ENCRYPT = os.getenv("DB_ENCRYPT", "no")
    DB_TRUST_SERVER_CERTIFICATE = os.getenv(
        "DB_TRUST_SERVER_CERTIFICATE",
        "yes",
    )

    # ==========================
    # Storage
    # ==========================
    CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
    MAX_FILE_SIZE_MB = 20

    def __init__(self):
        Path(self.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
        Path(self.CHROMA_PATH).mkdir(parents=True, exist_ok=True)

    @property
    def DATABASE_URL(self):
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

        return (
            "mssql+pyodbc:///?odbc_connect="
            + quote_plus(conn_str)
        )


settings = Settings()