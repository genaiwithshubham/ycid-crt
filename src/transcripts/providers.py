"""Concrete transcript provider implementations."""

import logging
from pathlib import Path
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, VideoUnavailable, NoTranscriptFound, CouldNotRetrieveTranscript

from src.transcripts.base import TranscriptProvider, TranscriptResult, TranscriptSegment

logger = logging.getLogger(__name__)


class YouTubeTranscriptProvider(TranscriptProvider):
    """Provider that fetches transcripts via YouTube's caption API.

    This uses the youtube-transcript-api library which accesses publicly
    available caption data. It does not bypass DRM or authentication.
    """

    def __init__(self, languages: list[str] | None = None):
        self.languages = languages or ["en", "en-US", "en-GB"]

    def get_transcript(self, video_id: str) -> Optional[TranscriptResult]:
        """Fetch transcript from YouTube."""
        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=self.languages)
            segments = [
                TranscriptSegment(
                    text=entry.text,
                    start=entry.start,
                    duration=entry.duration,
                )
                for entry in fetched
            ]
            return TranscriptResult(
                video_id=video_id,
                segments=segments,
                language=fetched.language_code,
                source="youtube_captions",
                is_generated=fetched.is_generated,
            )
        except TranscriptsDisabled:
            logger.info("Transcripts disabled for video %s", video_id)
            return None
        except VideoUnavailable:
            logger.info("Video unavailable for transcript: %s", video_id)
            return None
        except NoTranscriptFound:
            logger.info("No transcript found for video %s in languages %s", video_id, self.languages)
            return None
        except CouldNotRetrieveTranscript:
            logger.info("Could not retrieve transcript for video %s", video_id)
            return None
        except Exception as e:
            logger.warning("Unexpected error fetching transcript for %s: %s", video_id, e)
            return None

    def is_available(self, video_id: str) -> bool:
        """Check if transcript is available."""
        try:
            YouTubeTranscriptApi().list(video_id)
            return True
        except Exception:
            return False


class FileTranscriptProvider(TranscriptProvider):
    """Provider that reads transcripts from local files."""

    def __init__(self, transcript_dir: str):
        self.transcript_dir = Path(transcript_dir)

    def get_transcript(self, video_id: str) -> Optional[TranscriptResult]:
        """Read transcript from a local file."""
        file_path = self.transcript_dir / f"{video_id}.txt"
        if not file_path.exists():
            file_path = self.transcript_dir / f"{video_id}.json"
        if not file_path.exists():
            return None

        try:
            text = file_path.read_text(encoding="utf-8")
            # Simple format: treat entire file as one segment at 0:00
            segments = [TranscriptSegment(text=text.strip(), start=0.0, duration=0.0)]
            return TranscriptResult(
                video_id=video_id,
                segments=segments,
                language="en",
                source="file",
                is_generated=False,
            )
        except Exception as e:
            logger.error("Failed to read transcript file %s: %s", file_path, e)
            return None

    def is_available(self, video_id: str) -> bool:
        """Check if a transcript file exists."""
        txt = self.transcript_dir / f"{video_id}.txt"
        json_file = self.transcript_dir / f"{video_id}.json"
        return txt.exists() or json_file.exists()
