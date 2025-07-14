# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote_plus
# import logging
# Enable detailed SQL logging (optional but helpful during development)
# logging.basicConfig()
# logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# Safely encode password that contains special characters like @
username = "sa"
password = quote_plus("Sa@157")  # encodes '@' as '%40'
host = "192.168.157.51"
port = "9090"
database = "Attendance_System"
driver = "ODBC+Driver+17+for+SQL+Server"

# Build the SQLAlchemy connection URL
DATABASE_URL = (
    f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}"
    f"?driver={driver}&TrustServerCertificate=yes&charset=utf8mb4"
)

# Create engine and session
# engine = create_engine(DATABASE_URL,echo=True)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
