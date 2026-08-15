"""YouTube Data API client with rate limiting and error handling."""

import logging
import time
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import Config
from src.youtube.models import YouTubeVideo

logger = logging.getLogger(__name__)


class YouTubeClient:
    """Client for interacting with the YouTube Data API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.YOUTUBE_API_KEY
        if not self.api_key:
            raise ValueError("YouTube API key is required. Set YOUTUBE_API_KEY in .env")
        self.service = build("youtube", "v3", developerKey=self.api_key, cache_discovery=False)
        self._last_request_time: float = 0.0

    def _rate_limited_request(self, request):
        """Execute a request with rate limiting."""
        elapsed = time.time() - self._last_request_time
        delay = Config.SEARCH_DELAY_SECONDS
        if elapsed < delay:
            time.sleep(delay - elapsed)
        try:
            response = request.execute()
            self._last_request_time = time.time()
            return response
        except HttpError as e:
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                logger.error("YouTube API quota exceeded.")
                raise RuntimeError("YouTube API quota exceeded. Please try again later.") from e
            if e.resp.status == 400:
                logger.error("Invalid YouTube API request: %s", e)
                raise ValueError(f"Invalid API request: {e}") from e
            if e.resp.status in (500, 503):
                logger.warning("YouTube API server error (%s), retrying...", e.resp.status)
                time.sleep(2)
                return request.execute()
            logger.error("YouTube API error: %s", e)
            raise
        except Exception as e:
            logger.error("Network or unexpected error: %s", e)
            raise

    def search_videos(
        self,
        query: str,
        max_results: int = 50,
        published_after: Optional[str] = None,
    ) -> list[YouTubeVideo]:
        """Search YouTube for videos matching a query."""
        logger.info("Searching YouTube: %s", query)
        videos: list[YouTubeVideo] = []
        next_page_token: Optional[str] = None
        remaining = max_results

        while remaining > 0:
            page_size = min(remaining, 50)
            request = self.service.search().list(
                q=query,
                part="snippet",
                type="video",
                maxResults=page_size,
                pageToken=next_page_token,
                publishedAfter=published_after,
                relevanceLanguage="en",
            )
            try:
                response = self._rate_limited_request(request)
            except Exception as e:
                logger.error("Search failed for query '%s': %s", query, e)
                break

            items = response.get("items", [])
            if not items:
                break

            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
            if video_ids:
                details = self._get_video_details(video_ids)
                for item in items:
                    vid = item["id"].get("videoId")
                    if vid and vid in details:
                        video = self._parse_video(item, details[vid], query)
                        videos.append(video)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
            remaining -= len(items)

        logger.info("Found %d videos for query: %s", len(videos), query)
        return videos

    def _get_video_details(self, video_ids: list[str]) -> dict[str, dict]:
        """Fetch content details and statistics for video IDs."""
        details: dict[str, dict] = {}
        # API allows up to 50 IDs per request
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            request = self.service.videos().list(
                part="contentDetails,statistics,status,snippet",
                id=",".join(batch),
            )
            try:
                response = self._rate_limited_request(request)
                for item in response.get("items", []):
                    details[item["id"]] = item
            except Exception as e:
                logger.warning("Failed to fetch details for batch: %s", e)
        return details

    def _parse_video(self, search_item: dict, details: dict, query: str) -> YouTubeVideo:
        """Parse API response into a YouTubeVideo model."""
        from datetime import datetime

        snippet = search_item.get("snippet", {})
        content = details.get("contentDetails", {})
        statistics = details.get("statistics", {})
        status = details.get("status", {})

        # Parse ISO 8601 duration (e.g., PT5M30S)
        duration_str = content.get("duration", "")
        duration = self._parse_duration(duration_str)

        published_str = snippet.get("publishedAt", "")
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            published_at = datetime.utcnow()

        # Determine license
        license_type = status.get("license", "UNKNOWN")
        rights_status = self._classify_license(license_type)

        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = None
        for quality in ("high", "medium", "default"):
            if quality in thumbnails:
                thumbnail_url = thumbnails[quality]["url"]
                break

        return YouTubeVideo(
            video_id=search_item["id"]["videoId"],
            title=snippet.get("title", ""),
            channel_id=snippet.get("channelId", ""),
            channel_name=snippet.get("channelTitle", ""),
            published_at=published_at,
            description=snippet.get("description", ""),
            thumbnail_url=thumbnail_url,
            duration=duration,
            view_count=self._safe_int(statistics.get("viewCount")),
            like_count=self._safe_int(statistics.get("likeCount")),
            comment_count=self._safe_int(statistics.get("commentCount")),
            search_query=query,
            license_type=license_type,
            rights_status=rights_status,
            rights_notes=f"License type from API: {license_type}",
            rights_verified=False,
        )

    @staticmethod
    def _parse_duration(duration_str: str) -> Optional[int]:
        """Parse ISO 8601 duration to seconds."""
        if not duration_str:
            return None
        import re

        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
        if not match:
            return None
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _safe_int(value) -> Optional[int]:
        """Safely convert a value to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _classify_license(license_type: str) -> str:
        """Classify YouTube license type into rights status."""
        if license_type == "creativeCommon":
            return "CREATIVE_COMMONS"
        if license_type == "youtube":
            return "STANDARD_YOUTUBE_LICENSE"
        return "UNKNOWN"
