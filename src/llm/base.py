"""Abstract base class for LLM providers."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract interface for LLM-based transcript analysis."""

    @abstractmethod
    def analyze_transcript(self, transcript: str, subject: str, subject_type: str = "person") -> list[dict[str, Any]]:
        """Analyze a transcript and return interesting moments.

        Returns a list of moment dictionaries.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is properly configured."""
        ...

    @abstractmethod
    def analyze_frames(
        self, frame_descriptions: list[str], subject: str, subject_type: str = "person"
    ) -> list[dict[str, Any]]:
        """Analyze a list of frame descriptions and return interesting moments.

        Args:
            frame_descriptions: List of text descriptions of video frames
            subject: Subject name or description
            subject_type: "person" or "scene"

        Returns:
            List of moment dictionaries
        """
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
    def _build_analysis_prompt(transcript: str, subject: str, subject_type: str = "person") -> str:
        """Build the prompt for transcript analysis, dispatching by subject_type."""
        if subject_type == "scene":
            return f"""You are analyzing a video transcript to find a specific scene.

Target scene description: {subject}

Your task is to locate any moment(s) in the transcript that match this description — matching characters, actions, or setting.

IMPORTANT RULES:
- Only identify moments that are actually present in the transcript.
- Do NOT fabricate quotes, events, or timestamps.
- Every moment must reference actual timestamps from the transcript.
- If no matching scene is present, return an empty moments array — do not force a match.

For each matching moment, provide:
- start_time: timestamp in HH:MM:SS format (must match transcript)
- end_time: timestamp in HH:MM:SS format
- topic: brief topic label (max 5 words)
- summary: 1-2 sentence description of what happens in the scene
- hook: a compelling one-sentence hook describing the scene
- interest_score: integer 1-10 (10 = perfect match to described scene)
- reason: brief explanation of how this moment matches the scene description

Return ONLY a JSON object in this exact format:
{{
  "moments": [
    {{
      "start_time": "00:12:30",
      "end_time": "00:14:05",
      "topic": "Arjuna draws his bow",
      "summary": "Arjuna confronts a group of warriors on the battlefield and begins fighting.",
      "hook": "Arjuna stands alone against a hundred warriors in this pivotal battle scene.",
      "interest_score": 9,
      "reason": "Directly matches the described scene with key characters and action."
    }}
  ]
}}

Transcript:
{transcript}
"""
        # Default: person / interview mode
        return f"""You are an expert video content researcher analyzing a transcript of a video featuring {subject}.

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
      "summary": "{subject} discusses their experience working on a landmark project.",
      "hook": "{subject} reveals what really happened behind the scenes.",
      "interest_score": 9,
      "reason": "Strong personal story and highly recognizable topic."
    }}
  ]
}}

Transcript:
{transcript}
"""
