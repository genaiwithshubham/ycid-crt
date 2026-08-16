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
