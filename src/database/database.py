"""Database engine and session management."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import Config
from src.database.models import Base

# Ensure data directory exists
_db_url = Config.DATABASE_URL
if _db_url.startswith("sqlite:///"):
    db_path = Path(_db_url.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(_db_url, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all database tables and run idempotent migrations."""
    Base.metadata.create_all(bind=engine)

    # Idempotent migration: add subject / subject_type columns if absent
    with engine.connect() as conn:
        rows = conn.execute(__import__("sqlalchemy").text("PRAGMA table_info(videos)")).fetchall()
        existing_cols = {row[1] for row in rows}
        if "subject" not in existing_cols:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE videos ADD COLUMN subject VARCHAR(300) DEFAULT ''"
            ))
        if "subject_type" not in existing_cols:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE videos ADD COLUMN subject_type VARCHAR(20) DEFAULT 'person'"
            ))
        conn.commit()


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
