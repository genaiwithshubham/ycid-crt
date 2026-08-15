"""LLM provider factory."""

import logging

from src.config import Config
from src.llm.base import LLMProvider
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.ollama import OllamaProvider
from src.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


def get_llm_provider() -> LLMProvider:
    """Factory function to get the configured LLM provider."""
    provider_name = Config.LLM_PROVIDER.lower()

    if provider_name == "openai":
        provider = OpenAIProvider()
        if provider.is_available():
            logger.info("Using OpenAI LLM provider (model: %s)", Config.LLM_MODEL)
            return provider
        logger.warning("OpenAI provider selected but API key not configured")

    elif provider_name == "anthropic":
        provider = AnthropicProvider()
        if provider.is_available():
            logger.info("Using Anthropic LLM provider")
            return provider
        logger.warning("Anthropic provider selected but API key not configured")

    elif provider_name == "ollama":
        provider = OllamaProvider()
        if provider.is_available():
            logger.info("Using Ollama LLM provider (model: %s)", Config.LLM_MODEL)
            return provider
        logger.warning("Ollama provider selected but Ollama is not running")

    else:
        logger.error("Unknown LLM provider: %s", provider_name)

    # Fallback: try any available provider
    for fallback_name, FallbackClass in [("openai", OpenAIProvider), ("anthropic", AnthropicProvider), ("ollama", OllamaProvider)]:
        provider = FallbackClass()
        if provider.is_available():
            logger.info("Falling back to %s LLM provider", fallback_name)
            return provider

    raise RuntimeError(
        f"No LLM provider available. Configured provider: {provider_name}. "
        "Please set the appropriate API key in your .env file."
    )
