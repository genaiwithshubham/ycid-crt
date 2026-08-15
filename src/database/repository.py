"""Database repository for CRUD operations."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import InterestingMomentDB, TranscriptDB, VideoDB
from src.youtube.models import YouTubeVideo

logger = logging.getLogger(__name__)


class VideoRepository:
    """Repository for video-related database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_video_id(self, video_id: str) -> Optional[VideoDB]:
        """Fetch a video by its YouTube video ID."""
        return self.db.query(VideoDB).filter(VideoDB.video_id == video_id).first()

    def create_or_update(self, video: YouTubeVideo) -> VideoDB:
        """Insert a new video or update existing."""
        existing = self.get_by_video_id(video.video_id)
        if existing:
            existing.title = video.title
            existing.description = video.description
            existing.view_count = video.view_count
            existing.like_count = video.like_count
            existing.comment_count = video.comment_count
            existing.relevance_score = video.relevance_score
            existing.duration = video.duration
            existing.thumbnail_url = video.thumbnail_url
            existing.rights_status = video.rights_status
            existing.rights_notes = video.rights_notes
            existing.rights_verified = video.rights_verified
            existing.license_type = video.license_type or "UNKNOWN"
            self.db.commit()
            self.db.refresh(existing)
            return existing

        db_video = VideoDB(
            video_id=video.video_id,
            title=video.title,
            channel_id=video.channel_id,
            channel_name=video.channel_name,
            published_at=video.published_at,
            description=video.description,
            thumbnail_url=video.thumbnail_url,
            duration=video.duration,
            view_count=video.view_count,
            like_count=video.like_count,
            comment_count=video.comment_count,
            url=video.url,
            search_query=video.search_query,
            relevance_score=video.relevance_score,
            license_type=video.license_type or "UNKNOWN",
            rights_status=video.rights_status,
            rights_notes=video.rights_notes,
            rights_verified=video.rights_verified,
        )
        self.db.add(db_video)
        self.db.commit()
        self.db.refresh(db_video)
        return db_video

    def get_all(self, celebrity: Optional[str] = None, limit: Optional[int] = None) -> list[VideoDB]:
        """Fetch all videos, optionally filtered by celebrity name in title."""
        query = self.db.query(VideoDB)
        if celebrity:
            query = query.filter(VideoDB.title.ilike(f"%{celebrity}%"))
        query = query.order_by(VideoDB.relevance_score.desc())
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_by_id(self, video_id: str) -> Optional[VideoDB]:
        """Fetch video by video_id string."""
        return self.get_by_video_id(video_id)


class TranscriptRepository:
    """Repository for transcript operations."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, video_id: str, transcript: str, language: str = "en", source: str = "youtube", timestamped: bool = True) -> TranscriptDB:
        """Save or replace a transcript for a video."""
        existing = (
            self.db.query(TranscriptDB)
            .filter(TranscriptDB.video_id == video_id)
            .first()
        )
        if existing:
            existing.transcript = transcript
            existing.language = language
            existing.source = source
            existing.timestamped = timestamped
            self.db.commit()
            self.db.refresh(existing)
            return existing

        db_transcript = TranscriptDB(
            video_id=video_id,
            transcript=transcript,
            language=language,
            source=source,
            timestamped=timestamped,
        )
        self.db.add(db_transcript)
        self.db.commit()
        self.db.refresh(db_transcript)
        return db_transcript

    def get_by_video_id(self, video_id: str) -> Optional[TranscriptDB]:
        """Fetch transcript for a video."""
        return (
            self.db.query(TranscriptDB)
            .filter(TranscriptDB.video_id == video_id)
            .first()
        )


class MomentRepository:
    """Repository for interesting moment operations."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, video_id: str, moment_data: dict) -> InterestingMomentDB:
        """Save an interesting moment."""
        moment = InterestingMomentDB(
            video_id=video_id,
            start_time=moment_data.get("start_time", "00:00:00"),
            end_time=moment_data.get("end_time", "00:00:00"),
            start_seconds=moment_data.get("start_seconds", 0),
            end_seconds=moment_data.get("end_seconds", 0),
            topic=moment_data.get("topic", ""),
            summary=moment_data.get("summary", ""),
            hook=moment_data.get("hook", ""),
            interest_score=moment_data.get("interest_score", 0),
            reason=moment_data.get("reason", ""),
            requires_rights_review=moment_data.get("requires_rights_review", True),
        )
        self.db.add(moment)
        self.db.commit()
        self.db.refresh(moment)
        return moment

    def get_by_video_id(self, video_id: str) -> list[InterestingMomentDB]:
        """Fetch all moments for a video."""
        return (
            self.db.query(InterestingMomentDB)
            .filter(InterestingMomentDB.video_id == video_id)
            .order_by(InterestingMomentDB.interest_score.desc())
            .all()
        )

    def get_all(self, celebrity: Optional[str] = None, min_score: int = 0) -> list[InterestingMomentDB]:
        """Fetch all moments with optional filters."""
        query = self.db.query(InterestingMomentDB).join(VideoDB)
        if celebrity:
            query = query.filter(VideoDB.title.ilike(f"%{celebrity}%"))
        if min_score > 0:
            query = query.filter(InterestingMomentDB.interest_score >= min_score)
        return query.order_by(InterestingMomentDB.interest_score.desc()).all()
