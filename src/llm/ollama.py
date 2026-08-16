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
