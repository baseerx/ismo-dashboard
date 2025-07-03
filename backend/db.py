# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = (
    "mssql+pyodbc://sa:Sa@157@192.168.157.51:9090/Attendance_System"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&TrustServerCertificate=yes"
    "&charset=utf8mb4"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
