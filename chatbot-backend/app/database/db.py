from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config.settings import settings
from app.database.guard import install as install_read_only_guard

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # a pooled connection idle overnight is dead by morning
    pool_recycle=1800,
    echo=settings.DEBUG_SQL,
)

# HR data is read-only to this service; only its own three tables may be
# written. See app/database/guard.py.
install_read_only_guard(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
