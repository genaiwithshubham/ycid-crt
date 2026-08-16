"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """Application configuration."""

    # API Keys
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # LLM
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4000"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/youtube_research.db")

    # Search
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "50"))
    SEARCH_DELAY_SECONDS: float = float(os.getenv("SEARCH_DELAY_SECONDS", "1.0"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Image to Text
    IMAGE_TO_TEXT_ENABLED: bool = os.getenv("IMAGE_TO_TEXT_ENABLED", "false").lower() == "true"
    IMAGE_TO_TEXT_BASE_URL: str = os.getenv("IMAGE_TO_TEXT_BASE_URL", "https://integrate.api.nvidia.com/v1")
    IMAGE_TO_TEXT_API_KEY: str = os.getenv("IMAGE_TO_TEXT_API_KEY", "")
    IMAGE_TO_TEXT_MODEL: str = os.getenv("IMAGE_TO_TEXT_MODEL", "thinkingmachines/inkling")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of missing configs."""
        missing = []
        if not cls.YOUTUBE_API_KEY:
            missing.append("YOUTUBE_API_KEY")
        return missing
