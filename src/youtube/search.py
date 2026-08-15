"""YouTube search orchestration with deduplication."""

import logging
from collections.abc import Sequence

from src.youtube.client import YouTubeClient
from src.youtube.models import SearchConfig, YouTubeVideo

logger = logging.getLogger(__name__)


class VideoSearcher:
    """Orchestrates multi-query YouTube search with deduplication."""

    def __init__(self, client: YouTubeClient | None = None):
        self.client = client or YouTubeClient()

    def search(
        self,
        config: SearchConfig,
        max_total_results: int = 100,
    ) -> list[YouTubeVideo]:
        """Execute searches for all generated queries and deduplicate."""
        queries = config.generate_queries()
        all_videos: list[YouTubeVideo] = []
        seen_ids: set[str] = set()

        per_query = min(config.max_results_per_query, max(10, max_total_results // len(queries)))

        for query in queries:
            if len(all_videos) >= max_total_results:
                break
            try:
                results = self.client.search_videos(query, max_results=per_query)
                for video in results:
                    if video.video_id not in seen_ids:
                        seen_ids.add(video.video_id)
                        all_videos.append(video)
                if len(all_videos) >= max_total_results:
                    break
            except Exception as e:
                logger.error("Search query failed '%s': %s", query, e)
                continue

        logger.info("Total unique videos found: %d", len(all_videos))
        return all_videos

    @staticmethod
    def deduplicate_fuzzy(
        videos: Sequence[YouTubeVideo],
        title_threshold: float = 0.9,
    ) -> list[YouTubeVideo]:
        """Optional fuzzy deduplication based on title similarity.

        Uses simple normalized string comparison.
        For production, consider python-Levenshtein or difflib.
        """
        import difflib

        kept: list[YouTubeVideo] = []
        for video in videos:
            is_duplicate = False
            normalized_title = video.title.lower().strip()
            for existing in kept:
                existing_title = existing.title.lower().strip()
                similarity = difflib.SequenceMatcher(
                    None, normalized_title, existing_title
                ).ratio()
                if similarity >= title_threshold and video.channel_id == existing.channel_id:
                    is_duplicate = True
                    logger.debug(
                        "Fuzzy duplicate detected: '%s' ~ '%s' (%.2f)",
                        video.title,
                        existing.title,
                        similarity,
                    )
                    break
            if not is_duplicate:
                kept.append(video)
        logger.info("Fuzzy deduplication: %d -> %d videos", len(videos), len(kept))
        return kept
