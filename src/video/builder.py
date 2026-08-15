"""Video builder: downloads YouTube clip segments using yt-dlp --download-sections."""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ClipResult:
    """Result of a single clip build attempt."""

    moment_id: int
    video_id: str
    topic: str
    start_seconds: int
    end_seconds: int
    output_path: Path
    success: bool
    error: str = ""

    @property
    def duration(self) -> int:
        return self.end_seconds - self.start_seconds


class VideoBuilder:
    """Downloads clip segments directly from YouTube using yt-dlp --download-sections.

    Each moment is fetched as a standalone clip — no full-video download required.
    ffmpeg is optional: if installed, cuts are frame-accurate; otherwise yt-dlp
    snaps to the nearest keyframe (typically within a few seconds).
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_clips(self, moments: list[Any], celebrity: str) -> list[ClipResult]:
        """Download a direct clip for each moment. Returns one ClipResult per moment."""
        if not moments:
            return []

        missing = self._check_tools()
        if "yt-dlp" in missing:
            raise RuntimeError(
                "yt-dlp is not installed. Run: pip install yt-dlp"
            )

        has_ffmpeg = "ffmpeg" not in missing
        if not has_ffmpeg:
            logger.warning(
                "ffmpeg not found — clips will snap to the nearest keyframe. "
                "For frame-accurate cuts install ffmpeg: brew install ffmpeg"
            )

        celebrity_dir = self.output_dir / celebrity.lower().replace(" ", "_")
        celebrity_dir.mkdir(parents=True, exist_ok=True)

        results: list[ClipResult] = []
        for m in moments:
            slug = m.topic[:40].lower().replace(" ", "_").replace("/", "-")
            filename = f"{m.video_id}_{m.start_seconds}s_{slug}.mp4"
            clip_path = celebrity_dir / filename

            if clip_path.exists():
                logger.info("Clip already exists, skipping: %s", clip_path)
                results.append(ClipResult(
                    moment_id=m.id,
                    video_id=m.video_id,
                    topic=m.topic,
                    start_seconds=m.start_seconds,
                    end_seconds=m.end_seconds,
                    output_path=clip_path,
                    success=True,
                ))
                continue

            error = self._download_section(
                m.video_id, m.start_seconds, m.end_seconds, clip_path, has_ffmpeg
            )
            results.append(ClipResult(
                moment_id=m.id,
                video_id=m.video_id,
                topic=m.topic,
                start_seconds=m.start_seconds,
                end_seconds=m.end_seconds,
                output_path=clip_path if error is None else Path(""),
                success=error is None,
                error=error or "",
            ))

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_tools(self) -> list[str]:
        """Return names of tools that are not available on PATH."""
        missing = []
        for tool in ("yt-dlp", "ffmpeg"):
            try:
                subprocess.run([tool, "--version"], capture_output=True, check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                missing.append(tool)
        return missing

    def _download_section(
        self, video_id: str, start: int, end: int, output: Path, has_ffmpeg: bool
    ) -> str | None:
        """Download only [start, end] seconds of a YouTube video.

        Uses yt-dlp --download-sections to avoid fetching the whole file.
        Returns None on success, or an error string on failure.
        """
        url = f"https://www.youtube.com/watch?v={video_id}"

        # Without ffmpeg yt-dlp cannot merge separate video+audio streams, so
        # restrict to pre-merged single-file formats only.
        fmt = (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            if has_ffmpeg
            else "best[ext=mp4]/best"
        )

        cmd = [
            "yt-dlp",
            "--format", fmt,
            "--download-sections", f"*{start}-{end}",
            "--output", str(output),
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            url,
        ]
        if has_ffmpeg:
            cmd.append("--force-keyframes-at-cuts")

        logger.info("Downloading section %ds–%ds for %s", start, end, video_id)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return None
        except FileNotFoundError:
            return "yt-dlp not found. Run: pip install yt-dlp"
        except subprocess.CalledProcessError as exc:
            return exc.stderr.strip() or "yt-dlp exited with a non-zero status"
