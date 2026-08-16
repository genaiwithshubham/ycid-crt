"""Anthropic LLM provider implementation."""

import logging
from typing import Any

from anthropic import Anthropic

from src.config import Config
from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """LLM provider using Anthropic Claude API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or Config.ANTHROPIC_API_KEY
        self.model = model or "claude-3-5-sonnet-20241022"
        self.max_tokens = Config.LLM_MAX_TOKENS
        self.temperature = Config.LLM_TEMPERATURE
        self._client: Anthropic | None = None

    @property
    def client(self) -> Anthropic:
        if self._client is None:
            if not self.api_key:
                raise ValueError("Anthropic API key not configured")
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze_transcript(self, transcript: str, subject: str, subject_type: str = "person") -> list[dict[str, Any]]:
        """Analyze transcript using Anthropic Claude."""
        if not self.is_available():
            logger.error("Anthropic provider not available: missing API key")
            return []

        prompt = self._build_analysis_prompt(transcript, subject, subject_type)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system="You are a precise video content researcher. Only report moments actually present in the transcript. Never fabricate content. Return only valid JSON.",
                messages=[{"role": "user", "content": prompt}],
            )
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text
            return self._parse_json_response(content)
        except Exception as e:
            logger.error("Anthropic API error: %s", e)
            return []

    def analyze_frames(
        self, frame_descriptions: list[str], subject: str, subject_type: str = "person"
    ) -> list[dict[str, Any]]:
        if not self.is_available():
            logger.error("Anthropic provider not available: missing API key")
            return []

        combined_text = "\n\n".join(
            f"[Frame {i+1} at ~{desc.get('timestamp', 'unknown')}s]: {desc.get('description', '')}"
            for i, desc in enumerate(frame_descriptions)
        )

        prompt = self._build_frame_analysis_prompt(combined_text, subject, subject_type)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system="You are a precise video content researcher analyzing frame descriptions from a video. Only report moments actually supported by the descriptions. Never fabricate content. Return only valid JSON.",
                messages=[{"role": "user", "content": prompt}],
            )
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text
            return self._parse_json_response(content)
        except Exception as e:
            logger.error("Anthropic frame analysis error: %s", e)
            return []

    def _build_frame_analysis_prompt(
        self, frame_descriptions: str, subject: str, subject_type: str = "person"
    ) -> str:
        """Build the prompt for frame-based analysis."""
        if subject_type == "scene":
            return f"""You are analyzing frame descriptions from a video to find a specific scene.

Target scene description: {subject}

Frame descriptions (with approximate timestamps):
{frame_descriptions}

Your task is to locate any moment(s) in the frame descriptions that match this scene description — matching characters, actions, or setting.

IMPORTANT RULES:
- Only identify moments that are actually supported by the frame descriptions.
- Do NOT fabricate events, actions, or details.
- Every moment must reference actual frame descriptions.
- If no matching scene is present, return an empty moments array.

For each matching moment, provide:
- start_time: approximate timestamp in HH:MM:SS format (based on frame timestamps)
- end_time: approximate timestamp in HH:MM:SS format
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
"""
        return f"""You are an expert video content researcher analyzing frame descriptions from a video featuring {subject}.

Frame descriptions (with approximate timestamps):
{frame_descriptions}

Your task is to identify the most interesting, engaging, or viral-worthy moments based on these visual descriptions.

IMPORTANT RULES:
- Only identify moments that are actually supported by the frame descriptions.
- Do NOT fabricate events, statements, or details.
- Every moment must reference actual frame descriptions.
- If the descriptions are sparse or lack interesting content, return an empty moments array.

Look for these types of moments:
- Funny or humorous visual moments
- Emotional or touching scenes
- Surprising visual revelations
- Notable actions or interactions
- Career milestones or behind-the-scenes visual content
- Personal anecdotes visible in frames
- Memorable visual moments
- Content with viral potential

For each moment, provide:
- start_time: approximate timestamp in HH:MM:SS format (based on frame timestamps)
- end_time: approximate timestamp in HH:MM:SS format
- topic: brief topic label (max 5 words)
- summary: 1-2 sentence summary of what happens
- hook: a compelling one-sentence hook for social media
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
"""
