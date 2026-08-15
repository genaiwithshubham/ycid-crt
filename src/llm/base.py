"""Abstract base class for LLM providers."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract interface for LLM-based transcript analysis."""

    @abstractmethod
    def analyze_transcript(self, transcript: str, celebrity: str) -> list[dict[str, Any]]:
        """Analyze a transcript and return interesting moments.

        Returns a list of moment dictionaries.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is properly configured."""
        ...

    @staticmethod
    def _parse_json_response(content: str) -> list[dict[str, Any]]:
        """Parse and validate LLM JSON response."""
        # Try to extract JSON from markdown code blocks
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and "moments" in data:
                moments = data["moments"]
            elif isinstance(data, list):
                moments = data
            else:
                moments = []
            return moments
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON response: %s", e)
            logger.debug("Raw content: %s", content[:500])
            return []

    @staticmethod
    def _build_analysis_prompt(transcript: str, celebrity: str) -> str:
        """Build the prompt for transcript analysis."""
        return f"""You are an expert video content researcher analyzing a transcript of a video featuring {celebrity}.

Your task is to identify the most interesting, engaging, or viral-worthy moments in the transcript.

IMPORTANT RULES:
- Only identify moments that are actually present in the transcript.
- Do NOT fabricate quotes, statements, or events.
- Every moment must reference actual timestamps from the transcript.
- If the transcript is sparse or lacks interesting content, return an empty moments array.

Look for these types of moments:
- Funny or humorous exchanges
- Emotional or touching stories
- Surprising revelations or confessions
- Controversial statements or hot takes
- Career milestones or behind-the-scenes stories
- Personal anecdotes
- Interesting opinions on current topics
- Memorable quotes
- Strong opening hooks
- Content with viral potential

For each moment, provide:
- start_time: timestamp in HH:MM:SS format (must match transcript)
- end_time: timestamp in HH:MM:SS format
- topic: brief topic label (max 5 words)
- summary: 1-2 sentence summary of what happens
- hook: a compelling one-sentence hook for social media (do not quote verbatim if it risks misrepresentation)
- interest_score: integer 1-10 (10 = extremely interesting/viral)
- reason: brief explanation of why this moment is interesting

Return ONLY a JSON object in this exact format:
{{
  "moments": [
    {{
      "start_time": "00:03:21",
      "end_time": "00:03:58",
      "topic": "Friends behind the scenes",
      "summary": "Jennifer discusses her experience working on Friends.",
      "hook": "Jennifer reveals what really happened behind the scenes on Friends.",
      "interest_score": 9,
      "reason": "Strong personal story and highly recognizable topic."
    }}
  ]
}}

Transcript:
{transcript}
"""
