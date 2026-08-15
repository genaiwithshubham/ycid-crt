"""Abstract base class for transcript providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranscriptSegment:
    """A single transcript segment with timing."""

    text: str
    start: float  # seconds
    duration: float  # seconds

    @property
    def end(self) -> float:
        return self.start + self.duration

    def format_timestamp(self) -> str:
        """Format start time as HH:MM:SS."""
        total_seconds = int(self.start)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass
class TranscriptResult:
    """Result from a transcript provider."""

    video_id: str
    segments: list[TranscriptSegment]
    language: str
    source: str
    is_generated: bool = False

    @property
    def full_text(self) -> str:
        """Concatenate all segment texts."""
        return " ".join(seg.text for seg in self.segments)

    @property
    def timestamped_text(self) -> str:
        """Return transcript with timestamps."""
        lines = []
        for seg in self.segments:
            lines.append(f"[{seg.format_timestamp()}] {seg.text}")
        return "\n".join(lines)


class TranscriptProvider(ABC):
    """Abstract interface for transcript retrieval."""

    @abstractmethod
    def get_transcript(self, video_id: str) -> Optional[TranscriptResult]:
        """Retrieve transcript for a video.

        Returns None if transcript is unavailable.
        """
        ...

    @abstractmethod
    def is_available(self, video_id: str) -> bool:
        """Check if a transcript is available without fetching it."""
        ...
