"""JSON export functionality."""

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.database.repository import MomentRepository, VideoRepository

logger = logging.getLogger(__name__)


class JSONExporter:
    """Export research data to JSON files."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_videos(self, videos: list[Any], filename: str = "videos.json") -> Path:
        """Export videos to JSON."""
        path = self.output_dir / filename
        data = []
        for v in videos:
            data.append({
                "video_id": v.video_id,
                "title": v.title,
                "channel_name": v.channel_name,
                "published_at": v.published_at.isoformat() if v.published_at else None,
                "duration": v.duration,
                "view_count": v.view_count,
                "like_count": v.like_count,
                "comment_count": v.comment_count,
                "url": v.url,
                "relevance_score": v.relevance_score,
                "rights_status": v.rights_status,
                "rights_notes": v.rights_notes,
                "rights_verified": v.rights_verified,
                "thumbnail_url": v.thumbnail_url,
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"videos": data}, f, indent=2, ensure_ascii=False)
        logger.info("Exported %d videos to JSON: %s", len(videos), path)
        return path

    def export_moments(self, moments: list[Any], filename: str = "moments.json") -> Path:
        """Export moments to JSON."""
        path = self.output_dir / filename
        data = []
        for m in moments:
            data.append({
                "video_id": m.video_id,
                "start_time": m.start_time,
                "end_time": m.end_time,
                "start_seconds": m.start_seconds,
                "end_seconds": m.end_seconds,
                "duration": m.end_seconds - m.start_seconds,
                "topic": m.topic,
                "summary": m.summary,
                "hook": m.hook,
                "interest_score": m.interest_score,
                "reason": m.reason,
                "requires_rights_review": m.requires_rights_review,
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"moments": data}, f, indent=2, ensure_ascii=False)
        logger.info("Exported %d moments to JSON: %s", len(moments), path)
        return path

    def export_clip_manifest(self, moments: list[Any], filename: str = "clip_manifest.json") -> Path:
        """Export candidate clip manifest."""
        path = self.output_dir / filename
        clips = []
        for m in moments:
            clips.append({
                "video_id": m.video_id,
                "source_url": f"https://www.youtube.com/watch?v={m.video_id}",
                "start": m.start_seconds,
                "end": m.end_seconds,
                "duration": m.end_seconds - m.start_seconds,
                "topic": m.topic,
                "hook": m.hook,
                "interest_score": m.interest_score,
                "rights_status": "UNKNOWN",
                "requires_rights_review": True,
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"clips": clips}, f, indent=2, ensure_ascii=False)
        logger.info("Exported %d clip candidates to %s", len(clips), path)
        return path

    def export_all(self, db: Session, celebrity: str) -> dict[str, Path]:
        """Export all data for a celebrity."""
        video_repo = VideoRepository(db)
        moment_repo = MomentRepository(db)

        videos = video_repo.get_all(celebrity=celebrity)
        moments = moment_repo.get_all(celebrity=celebrity)

        base_name = celebrity.lower().replace(" ", "_")
        return {
            "videos": self.export_videos(videos, f"{base_name}_videos.json"),
            "moments": self.export_moments(moments, f"{base_name}_moments.json"),
            "clips": self.export_clip_manifest(moments, f"{base_name}_clip_manifest.json"),
        }