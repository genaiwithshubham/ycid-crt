"""Interesting moment detection using LLM analysis."""

import logging
import re
from typing import Any

from src.llm.base import LLMProvider
from src.transcripts.base import TranscriptResult

logger = logging.getLogger(__name__)


class MomentAnalyzer:
    """Analyzes transcripts to identify interesting moments."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def analyze(
        self,
        transcript: TranscriptResult,
        subject: str,
        subject_type: str = "person",
    ) -> list[dict[str, Any]]:
        """Analyze a transcript and return interesting moments."""
        if not transcript.segments:
            logger.info("No transcript segments to analyze for %s", transcript.video_id)
            return []

        text = transcript.timestamped_text
        # Truncate if extremely long to avoid token limits
        max_chars = 15000
        if len(text) > max_chars:
            logger.warning(
                "Transcript for %s truncated from %d to %d chars",
                transcript.video_id,
                len(text),
                max_chars,
            )
            text = text[:max_chars] + "\n...[transcript truncated]"

        logger.info("Analyzing transcript for %s (%d chars)", transcript.video_id, len(text))
        moments = self.llm.analyze_transcript(text, subject, subject_type)

        # Enrich moments with computed fields
        for moment in moments:
            moment["video_id"] = transcript.video_id
            moment["start_seconds"] = self._parse_timestamp(moment.get("start_time", "00:00:00"))
            moment["end_seconds"] = self._parse_timestamp(moment.get("end_time", "00:00:00"))
            moment["duration"] = moment["end_seconds"] - moment["start_seconds"]
            moment["requires_rights_review"] = True
            moment["source_transcript"] = transcript.source

        logger.info("Found %d interesting moments for %s", len(moments), transcript.video_id)
        return moments

    @staticmethod
    def _parse_timestamp(ts: str) -> int:
        """Parse HH:MM:SS or MM:SS to seconds."""
        ts = ts.strip()
        parts = ts.split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 1:
                return int(parts[0])
        except ValueError:
            pass
        return 0

    def analyze_batch(
        self,
        transcripts: list[TranscriptResult],
        subject: str,
        subject_type: str = "person",
    ) -> list[dict[str, Any]]:
        """Analyze multiple transcripts."""
        all_moments = []
        for transcript in transcripts:
            try:
                moments = self.analyze(transcript, subject, subject_type)
                all_moments.extend(moments)
            except Exception as e:
                logger.error("Failed to analyze transcript %s: %s", transcript.video_id, e)
                continue
        return all_moments
