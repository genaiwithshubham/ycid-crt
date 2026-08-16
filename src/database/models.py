"""SQLAlchemy ORM models for the research database."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class VideoDB(Base):
    """Database model for discovered videos."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    video_id = Column(String(16), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    channel_id = Column(String(32), nullable=False)
    channel_name = Column(String(200), nullable=False)
    published_at = Column(DateTime, nullable=False)
    description = Column(Text, default="")
    thumbnail_url = Column(String(500), nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    view_count = Column(Integer, nullable=True)
    like_count = Column(Integer, nullable=True)
    comment_count = Column(Integer, nullable=True)
    url = Column(String(200), nullable=False)
    search_query = Column(String(200), default="")
    relevance_score = Column(Integer, default=0)
    subject = Column(String(300), default="")
    subject_type = Column(String(20), default="person")

    # Rights
    license_type = Column(String(50), default="UNKNOWN")
    rights_status = Column(String(50), default="UNKNOWN")
    rights_notes = Column(Text, default="")
    rights_verified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transcripts = relationship("TranscriptDB", back_populates="video", cascade="all, delete-orphan")
    moments = relationship("InterestingMomentDB", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VideoDB(id={self.video_id}, title={self.title[:50]!r})>"


class TranscriptDB(Base):
    """Database model for video transcripts."""

    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True)
    video_id = Column(String(16), ForeignKey("videos.video_id"), nullable=False, index=True)
    transcript = Column(Text, nullable=False)
    language = Column(String(10), default="en")
    source = Column(String(50), default="youtube")  # youtube, file, manual, etc.
    timestamped = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("VideoDB", back_populates="transcripts")

    def __repr__(self) -> str:
        return f"<TranscriptDB(video_id={self.video_id}, lang={self.language})>"


class InterestingMomentDB(Base):
    """Database model for interesting moments identified by LLM analysis."""

    __tablename__ = "interesting_moments"

    id = Column(Integer, primary_key=True)
    video_id = Column(String(16), ForeignKey("videos.video_id"), nullable=False, index=True)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    start_seconds = Column(Integer, nullable=False)
    end_seconds = Column(Integer, nullable=False)
    topic = Column(String(200), nullable=False)
    summary = Column(Text, nullable=False)
    hook = Column(Text, default="")
    interest_score = Column(Integer, default=0)
    reason = Column(Text, default="")
    requires_rights_review = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("VideoDB", back_populates="moments")

    def __repr__(self) -> str:
        return f"<InterestingMomentDB(video_id={self.video_id}, topic={self.topic[:50]!r})>"
