"""Ollama LLM provider implementation."""

import logging
from typing import Any

from ollama import AsyncClient, ChatResponse, chat

from src.config import Config
from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider using a local Ollama instance."""

    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or Config.LLM_MODEL
        self.host = host
        self.max_tokens = Config.LLM_MAX_TOKENS
        self.temperature = Config.LLM_TEMPERATURE

    def is_available(self) -> bool:
        try:
            import ollama

            client = ollama.Client(host=self.host) if self.host else ollama.Client()
            client.list()
            return True
        except Exception:
            return False

    def analyze_transcript(self, transcript: str, subject: str, subject_type: str = "person") -> list[dict[str, Any]]:
        """Analyze transcript using a local Ollama model."""
        if not self.is_available():
            logger.error("Ollama provider not available: ensure Ollama is running")
            return []

        prompt = self._build_analysis_prompt(transcript, subject, subject_type)

        try:
            response: ChatResponse = chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise video content researcher. Only report moments actually present in the transcript. Never fabricate content. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                options={
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                },
            )
            content = response.message.content or ""
            return self._parse_json_response(content)
        except Exception as e:
            logger.error("Ollama API error: %s", e)
            return []

    def analyze_frames(
        self, frame_descriptions: list[str], subject: str, subject_type: str = "person"
    ) -> list[dict[str, Any]]:
        if not self.is_available():
            logger.error("Ollama provider not available: ensure Ollama is running")
            return []

        combined_text = "\n\n".join(
            f"[Frame {i+1} at ~{desc.get('timestamp', 'unknown')}s]: {desc.get('description', '')}"
            for i, desc in enumerate(frame_descriptions)
        )

        prompt = self._build_frame_analysis_prompt(combined_text, subject, subject_type)

        try:
            response: ChatResponse = chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise video content researcher analyzing frame descriptions from a video. Only report moments actually supported by the descriptions. Never fabricate content. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                options={
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                },
            )
            content = response.message.content or ""
            return self._parse_json_response(content)
        except Exception as e:
            logger.error("Ollama frame analysis error: %s", e)
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

    async def analyze_transcript_stream(
        self, transcript: str, subject: str, subject_type: str = "person"
    ) -> list[dict[str, Any]]:
        """Analyze transcript using streaming (async)."""
        if not self.is_available():
            logger.error("Ollama provider not available: ensure Ollama is running")
            return []

        prompt = self._build_analysis_prompt(transcript, subject, subject_type)
        content = ""

        try:
            client = AsyncClient(host=self.host) if self.host else AsyncClient()
            async for part in await client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise video content researcher. Only report moments actually present in the transcript. Never fabricate content. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                stream=True,
                options={
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                },
            ):
                content += part["message"]["content"]
            return self._parse_json_response(content)
        except Exception as e:
            logger.error("Ollama streaming error: %s", e)
            return []
