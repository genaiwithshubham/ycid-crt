"""Markdown report generation."""

import logging
from pathlib import Path
from typing import Sequence

from sqlalchemy.orm import Session

from src.database.models import InterestingMomentDB, VideoDB
from src.database.repository import MomentRepository, VideoRepository

logger = logging.getLogger(__name__)


class MarkdownReport:
    """Generate a Markdown research report."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        db: Session,
        celebrity: str,
        filename: str | None = None,
    ) -> Path:
        """Generate a full Markdown report."""
        if filename is None:
            filename = f"{celebrity.lower().replace(' ', '_')}_report.md"

        path = self.output_dir / filename

        video_repo = VideoRepository(db)
        moment_repo = MomentRepository(db)

        videos = video_repo.get_all(celebrity=celebrity)
        moments = moment_repo.get_all(celebrity=celebrity)

        lines = [
            f"# {celebrity} — YouTube Interview Research Report",
            "",
            f"**Generated:** {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Videos analyzed:** {len(videos)}",
            f"**Interesting moments found:** {len(moments)}",
            "",
            "---",
            "",
            "## ⚠️ Copyright & Licensing Notice",
            "",
            "> **Finding a video on YouTube does NOT grant you rights to reproduce, publish, or distribute it.**",
            "> ",
            "> All videos listed in this report are subject to copyright. Reuse requires explicit permission",
            "> from the rights holder or a valid license. This tool is for **research and discovery only**.",
            "",
            "---",
            "",
            "## Top Videos",
            "",
        ]

        for i, video in enumerate(videos[:20], 1):
            lines.extend(self._format_video(i, video))

        lines.extend([
            "",
            "---",
            "",
            "## Interesting Moments",
            "",
        ])

        if not moments:
            lines.append("_No interesting moments were identified in the analyzed transcripts._")
        else:
            for moment in moments:
                lines.extend(self._format_moment(moment))

        lines.extend([
            "",
            "---",
            "",
            "## Candidate Clip Manifest",
            "",
            "The following clips are **candidates for human review only**. Do not create or publish",
            "clips without obtaining proper rights clearance.",
            "",
            "```json",
        ])

        clips = []
        for m in moments:
            clips.append({
                "video_id": m.video_id,
                "source_url": f"https://www.youtube.com/watch?v={m.video_id}",
                "start": m.start_seconds,
                "end": m.end_seconds,
                "duration": m.end_seconds - m.start_seconds,
                "topic": m.topic,
                "hook": m.hook,
                "interest_score": m.interest_score,
                "rights_status": "UNKNOWN",
                "requires_rights_review": True,
            })

        import json
        lines.append(json.dumps({"clips": clips}, indent=2))
        lines.append("```")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("Report generated: %s", path)
        return path

    def _format_video(self, rank: int, video: VideoDB) -> list[str]:
        """Format a video entry for the report."""
        duration_str = "Unknown"
        if video.duration:
            m, s = divmod(video.duration, 60)
            h, m = divmod(m, 60)
            duration_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        rights_badge = "⚠️ UNKNOWN" if video.rights_status == "UNKNOWN" else video.rights_status
        if video.rights_status == "CREATIVE_COMMONS":
            rights_badge += " (verify independently)"

        return [
            f"### {rank}. {video.title}",
            "",
            f"- **Channel:** {video.channel_name}",
            f"- **Duration:** {duration_str}",
            f"- **Views:** {video.view_count or 'N/A'}",
            f"- **Score:** {video.relevance_score}",
            f"- **Rights:** {rights_badge}",
            f"- **URL:** {video.url}",
            "",
        ]

    def _format_moment(self, moment: InterestingMomentDB) -> list[str]:
        """Format an interesting moment for the report."""
        duration = moment.end_seconds - moment.start_seconds
        return [
            f"### {moment.start_time} – {moment.topic}",
            "",
            f"**Video:** [{moment.video_id}](https://www.youtube.com/watch?v={moment.video_id})",
            f"**Interest Score:** {moment.interest_score}/10",
            f"**Duration:** {duration}s",
            "",
            "**Summary:**",
            f"{moment.summary}",
            "",
            "**Potential Hook:**",
            f"_{moment.hook}_",
            "",
            "**Reason:**",
            f"{moment.reason}",
            "",
            "**Rights Review:**",
            "⚠️ **Required** — Do not publish without clearance.",
            "",
            "---",
            "",
        ]