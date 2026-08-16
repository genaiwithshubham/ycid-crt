"""OpenAI LLM provider implementation."""

import base64
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI

from src.config import Config
from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)


def _encode_image_to_base64(image_path: Path) -> str:
    """Encode an image file to base64 data URL."""
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    # Determine MIME type from extension
    suffix = image_path.suffix.lower()
    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/jpeg")
    return f"data:{mime_type};base64,{encoded}"


class OpenAIProvider(LLMProvider):
    """LLM provider using OpenAI API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or Config.OPENAI_API_KEY
        self.model = model or Config.LLM_MODEL
        self.max_tokens = Config.LLM_MAX_TOKENS
        self.temperature = Config.LLM_TEMPERATURE
        self._client: OpenAI | None = None
        self._image_client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API key not configured")
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    @property
    def image_client(self) -> OpenAI | None:
        if not Config.IMAGE_TO_TEXT_ENABLED:
            return None
        if self._image_client is None:
            if not Config.IMAGE_TO_TEXT_API_KEY:
                logger.warning("IMAGE_TO_TEXT_ENABLED is true but IMAGE_TO_TEXT_API_KEY not configured")
                return None
            self._image_client = OpenAI(
                base_url=Config.IMAGE_TO_TEXT_BASE_URL,
                api_key=Config.IMAGE_TO_TEXT_API_KEY,
            )
        return self._image_client

    def is_image_to_text_available(self) -> bool:
        return Config.IMAGE_TO_TEXT_ENABLED and bool(Config.IMAGE_TO_TEXT_API_KEY)

    def describe_image(self, image_url: str, prompt: str = "Describe this image in detail.") -> str:
        if not self.is_image_to_text_available():
            logger.error("Image to text not available: IMAGE_TO_TEXT_ENABLED=%s, API_KEY configured=%s",
                         Config.IMAGE_TO_TEXT_ENABLED, bool(Config.IMAGE_TO_TEXT_API_KEY))
            return ""

        client = self.image_client
        if not client:
            return ""

        # If it's a local file path, encode as base64
        if image_url.startswith("file://"):
            image_path = Path(image_url[7:])  # Remove file:// prefix
            if image_path.exists():
                image_url = _encode_image_to_base64(image_path)
            else:
                logger.error("Image file not found: %s", image_path)
                return ""

        try:
            response = client.chat.completions.create(
                model=Config.IMAGE_TO_TEXT_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("Image to text API error: %s", e)
            return ""

    def analyze_frames(
        self, frame_descriptions: list[str], subject: str, subject_type: str = "person"
    ) -> list[dict[str, Any]]:
        if not self.is_available():
            logger.error("OpenAI provider not available: missing API key")
            return []

        combined_text = "\n\n".join(
            f"[Frame {i+1} at ~{desc.get('timestamp', 'unknown')}s]: {desc.get('description', '')}"
            for i, desc in enumerate(frame_descriptions)
        )

        prompt = self._build_frame_analysis_prompt(combined_text, subject, subject_type)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise video content researcher analyzing frame descriptions from a video. Only report moments actually supported by the descriptions. Never fabricate content. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return self._parse_json_response(content)
        except Exception as e:
            logger.error("OpenAI frame analysis error: %s", e)
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

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze_transcript(self, transcript: str, subject: str, subject_type: str = "person") -> list[dict[str, Any]]:
        """Analyze transcript using OpenAI."""
        if not self.is_available():
            logger.error("OpenAI provider not available: missing API key")
            return []

        prompt = self._build_analysis_prompt(transcript, subject, subject_type)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise video content researcher. Only report moments actually present in the transcript. Never fabricate content.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return self._parse_json_response(content)
        except Exception as e:
            logger.error("OpenAI API error: %s", e)
            return []
