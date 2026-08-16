"""CSV export functionality."""

import csv
import logging
from pathlib import Path
from typing import Sequence

from sqlalchemy.orm import Session

from src.database.models import InterestingMomentDB, VideoDB
from src.database.repository import MomentRepository, VideoRepository
from src.utils import slugify

logger = logging.getLogger(__name__)


class CSVExporter:
    """Export research data to CSV files."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_videos(self, videos: Sequence[VideoDB], filename: str = "videos.csv") -> Path:
        """Export video metadata to CSV."""
        path = self.output_dir / filename
        fieldnames = [
            "video_id", "title", "channel_name", "published_at",
            "duration", "view_count", "like_count", "comment_count",
            "url", "relevance_score", "rights_status", "rights_verified",
            "search_query",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for video in videos:
                writer.writerow({
                    "video_id": video.video_id,
                    "title": video.title,
                    "channel_name": video.channel_name,
                    "published_at": video.published_at.isoformat() if video.published_at else "",
                    "duration": video.duration,
                    "view_count": video.view_count,
                    "like_count": video.like_count,
                    "comment_count": video.comment_count,
                    "url": video.url,
                    "relevance_score": video.relevance_score,
                    "rights_status": video.rights_status,
                    "rights_verified": video.rights_verified,
                    "search_query": video.search_query,
                })
        logger.info("Exported %d videos to %s", len(videos), path)
        return path

    def export_moments(self, moments: Sequence[InterestingMomentDB], filename: str = "moments.csv") -> Path:
        """Export interesting moments to CSV."""
        path = self.output_dir / filename
        fieldnames = [
            "video_id", "start_time", "end_time", "duration_seconds",
            "topic", "summary", "hook", "interest_score", "reason",
            "requires_rights_review",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in moments:
                writer.writerow({
                    "video_id": m.video_id,
                    "start_time": m.start_time,
                    "end_time": m.end_time,
                    "duration_seconds": m.end_seconds - m.start_seconds,
                    "topic": m.topic,
                    "summary": m.summary,
                    "hook": m.hook,
                    "interest_score": m.interest_score,
                    "reason": m.reason,
                    "requires_rights_review": m.requires_rights_review,
                })
        logger.info("Exported %d moments to %s", len(moments), path)
        return path

    def export_all(self, db: Session, subject: str) -> dict[str, Path]:
        """Export all data for a subject."""
        video_repo = VideoRepository(db)
        moment_repo = MomentRepository(db)

        videos = video_repo.get_all(subject=subject)
        moments = moment_repo.get_all(subject=subject)

        base = slugify(subject)
        return {
            "videos": self.export_videos(videos, f"{base}_videos.csv"),
            "moments": self.export_moments(moments, f"{base}_moments.csv"),
        }