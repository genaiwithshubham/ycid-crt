"""Configurable relevance scoring for discovered videos."""

import logging
from dataclasses import dataclass, field

from src.youtube.models import YouTubeVideo

logger = logging.getLogger(__name__)


@dataclass
class ScoringRule:
    """A single scoring rule."""

    name: str
    points: int
    condition: str  # description for logging


@dataclass
class ScoringConfig:
    """Configuration for the relevance scoring system."""

    subject: str
    subject_type: str = "person"
    rules: list[ScoringRule] = field(default_factory=list)
    min_duration_seconds: int = 300  # 5 minutes
    duration_bonus: int = 1

    DEFAULT_RULES: list[ScoringRule] = field(
        default_factory=lambda: [
            ScoringRule("title_subject", 5, "subject name in title"),
            ScoringRule("desc_subject", 3, "subject name in description"),
            ScoringRule("title_interview", 3, 'interview" in title'),
            ScoringRule("title_podcast", 2, '"podcast" in title'),
            ScoringRule("title_appearance", 2, '"appearance" in title'),
            ScoringRule("title_talks", 2, '"talks about" in title'),
            ScoringRule("title_redcarpet", 1, '"red carpet" in title'),
            ScoringRule("title_latenight", 1, '"late night" in title'),
            ScoringRule("title_funny", 1, '"funny" in title'),
            ScoringRule("title_full", 1, '"full" in title'),
        ]
    )

    def __post_init__(self):
        if not self.rules:
            self.rules = self.DEFAULT_RULES


class RelevanceScorer:
    """Scores videos based on configurable rules."""

    PERSON_KEYWORD_SCORES: dict = {
        "interview": 3,
        "podcast": 2,
        "appearance": 2,
        "talks about": 2,
        "red carpet": 1,
        "late night": 1,
        "funny": 1,
        "full interview": 2,
        "behind the scenes": 2,
        "story": 1,
        "reveal": 1,
        "secret": 1,
    }

    SCENE_KEYWORD_SCORES: dict = {
        "scene": 3,
        "full scene": 3,
        "clip": 2,
        "fight": 2,
        "battle": 2,
        "duel": 2,
        "episode": 2,
        "full episode": 3,
        "hd": 1,
        "movie clip": 2,
    }

    def __init__(self, config: ScoringConfig):
        self.config = config
        self.subject_lower = config.subject.lower()
        self.subject_parts = [p.strip() for p in config.subject.lower().split() if len(p.strip()) > 2]
        self._keyword_scores = (
            self.PERSON_KEYWORD_SCORES if config.subject_type == "person" else self.SCENE_KEYWORD_SCORES
        )

    def score(self, video: YouTubeVideo) -> int:
        """Calculate relevance score for a video."""
        score = 0
        title_lower = video.title.lower()
        desc_lower = video.description.lower()

        # Subject name in title
        if self._name_in_text(title_lower):
            score += 5
            logger.debug("+5 for subject in title: %s", video.video_id)

        # Subject name in description
        if self._name_in_text(desc_lower):
            score += 3
            logger.debug("+3 for subject in description: %s", video.video_id)

        # Keyword bonuses in title
        for keyword, points in self._keyword_scores.items():
            if keyword in title_lower:
                score += points
                logger.debug("+%d for '%s' in title: %s", points, keyword, video.video_id)

        # Duration bonus
        if video.duration and video.duration >= self.config.min_duration_seconds:
            score += self.config.duration_bonus
            logger.debug("+1 for duration >= 5min: %s", video.video_id)

        # View count bonus (logarithmic)
        if video.view_count and video.view_count > 100000:
            score += min(5, video.view_count // 1000000)
            logger.debug("+view bonus for: %s", video.video_id)

        video.relevance_score = score
        return score

    def _name_in_text(self, text: str) -> bool:
        """Check if subject name appears in text."""
        if self.subject_lower in text:
            return True
        # For multi-word names, check all significant parts
        if len(self.subject_parts) > 1:
            return all(part in text for part in self.subject_parts)
        return False

    def score_videos(self, videos: list[YouTubeVideo]) -> list[YouTubeVideo]:
        """Score and sort videos by relevance."""
        for video in videos:
            self.score(video)
        videos.sort(key=lambda v: v.relevance_score, reverse=True)
        return videos
