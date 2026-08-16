"""Video frame extraction utilities."""

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_frames(
    video_id: str,
    interval_seconds: int = 30,
    max_frames: int = 10,
    output_dir: Path | None = None,
) -> list[Path]:
    """Extract frames from a YouTube video at regular intervals.

    Args:
        video_id: YouTube video ID
        interval_seconds: Seconds between extracted frames
        max_frames: Maximum number of frames to extract
        output_dir: Directory to save frames (uses temp dir if not provided)

    Returns:
        List of paths to extracted frame images
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix=f"frames_{video_id}_"))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    # First, get video duration using yt-dlp
    duration = _get_video_duration(url)
    if duration <= 0:
        logger.warning("Could not determine video duration for %s", video_id)
        return []

    # Calculate frame timestamps
    timestamps = []
    current = interval_seconds
    while current < duration and len(timestamps) < max_frames:
        timestamps.append(current)
        current += interval_seconds

    if not timestamps:
        return []

    frame_paths = []
    for i, ts in enumerate(timestamps):
        output_path = output_dir / f"frame_{i:03d}_{ts}s.jpg"
        if _extract_frame_at_timestamp(url, ts, output_path):
            frame_paths.append(output_path)
        else:
            logger.warning("Failed to extract frame at %ds for %s", ts, video_id)

    return frame_paths


def _get_video_duration(url: str) -> float:
    """Get video duration in seconds using yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--skip-download", "--print", "%(duration)s", url],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        duration_str = result.stdout.strip()
        return float(duration_str) if duration_str else 0.0
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
        logger.error("Failed to get video duration: %s", e)
        return 0.0


def _extract_frame_at_timestamp(url: str, timestamp: float, output_path: Path) -> bool:
    """Extract a single frame at the given timestamp using yt-dlp + ffmpeg."""
    try:
        # Use yt-dlp with ffmpeg as external downloader to seek and extract frame
        # This avoids expired direct URLs by letting yt-dlp handle auth/cookies
        seek_time = max(0, timestamp - 2)
        duration = 5

        cmd = [
            "yt-dlp",
            "-f", "best[ext=mp4]/best",
            "--external-downloader", "ffmpeg",
            "--external-downloader-args", f"ffmpeg_i:-ss {seek_time} -t {duration}",
            "-o", "-",  # Output to stdout
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, check=True, timeout=60)

        if not result.stdout:
            return False

        # Extract frame from the downloaded segment
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", "pipe:0",
            "-ss", str(timestamp - seek_time),
            "-vframes", "1",
            "-q:v", "2",
            "-y",
            str(output_path),
        ]
        subprocess.run(ffmpeg_cmd, input=result.stdout, capture_output=True, check=True, timeout=30)
        return output_path.exists()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.error("Failed to extract frame at %ds: %s", timestamp, e)
        return False


def cleanup_frames(frame_paths: list[Path]) -> None:
    """Clean up extracted frame files."""
    for path in frame_paths:
        try:
            if path.exists():
                path.unlink()
        except OSError as e:
            logger.warning("Failed to delete frame %s: %s", path, e)