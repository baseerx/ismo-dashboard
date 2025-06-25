# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Example for PostgreSQL: replace with your actual DB info
DATABASE_URL = "mysql+pymysql://root:@localhost:3306/attendance_system?charset=utf8mb4"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
