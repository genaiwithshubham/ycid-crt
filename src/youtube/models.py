"""Data models for YouTube video metadata."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class YouTubeVideo:
    """Represents a discovered YouTube video."""

    video_id: str
    title: str
    channel_id: str
    channel_name: str
    published_at: datetime
    description: str
    thumbnail_url: Optional[str] = None
    duration: Optional[int] = None  # seconds
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    url: str = ""
    search_query: str = ""
    relevance_score: int = 0
    license_type: Optional[str] = None
    rights_status: str = "UNKNOWN"
    rights_notes: str = ""
    rights_verified: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.url:
            self.url = f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def duration_formatted(self) -> str:
        """Return duration as HH:MM:SS or MM:SS."""
        if self.duration is None:
            return "Unknown"
        minutes, seconds = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


@dataclass
class SearchConfig:
    """Configuration for search query generation."""

    celebrity: str
    keywords: list[str] = field(default_factory=list)
    max_results_per_query: int = 50

    DEFAULT_KEYWORDS: list[str] = field(
        default_factory=lambda: [
            "interview",
            "full interview",
            "podcast",
            "appearance",
            "talks about",
            "funny interview",
            "red carpet",
            "late night",
            "celebrity interview",
        ]
    )

    def __post_init__(self):
        if not self.keywords:
            self.keywords = self.DEFAULT_KEYWORDS

    def generate_queries(self) -> list[str]:
        """Generate search queries from celebrity name and keywords."""
        queries = [f'{self.celebrity} {kw}' for kw in self.keywords]
        # Also add the celebrity name alone as a fallback
        queries.append(self.celebrity)
        return queries
