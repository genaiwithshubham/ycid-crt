"""CLI entry point for the YouTube Celebrity Interview Research Tool."""

import logging
import sys
from pathlib import Path

import typer
from sqlalchemy.orm import Session

from src.analysis.moments import MomentAnalyzer
from src.config import Config
from src.database.database import SessionLocal, init_db
from src.database.repository import MomentRepository, TranscriptRepository, VideoRepository
from src.export.csv_export import CSVExporter
from src.export.json_export import JSONExporter
from src.export.markdown_report import MarkdownReport
from src.llm import get_llm_provider
from src.rights.classifier import RightsClassifier
from src.scoring.relevance import RelevanceScorer, ScoringConfig
from src.transcripts.providers import YouTubeTranscriptProvider
from src.utils import slugify
from src.video.builder import VideoBuilder
from src.youtube.models import SearchConfig
from src.youtube.search import VideoSearcher

app = typer.Typer(
    name="youtube-research",
    help="Discover, analyze, and research YouTube interviews and clips.",
    add_completion=False,
)


def setup_logging() -> None:
    """Configure structured logging."""
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def get_db_session() -> Session:
    """Get a database session."""
    return SessionLocal()


@app.command()
def search(
    subject: str = typer.Option(..., "--subject", "-s", help="Subject to search for (person or scene description)"),
    subject_type: str = typer.Option("person", "--type", "-t", help="Subject type: person or scene"),
    keywords: str = typer.Option(
        "",
        "--keywords",
        "-k",
        help="Comma-separated search keywords (overrides defaults for the subject type)",
    ),
    max_results: int = typer.Option(50, "--max-results", "-m", help="Maximum total results"),
    fuzzy_dedup: bool = typer.Option(False, "--fuzzy-dedup", help="Enable fuzzy title deduplication"),
) -> None:
    """Search YouTube for videos and store metadata."""
    setup_logging()
    logger = logging.getLogger(__name__)

    if subject_type not in {"person", "scene"}:
        typer.echo(f"ERROR: --type must be 'person' or 'scene', got '{subject_type}'", err=True)
        raise typer.Exit(1)

    missing = Config.validate()
    if missing:
        typer.echo(f"ERROR: Missing configuration: {', '.join(missing)}", err=True)
        typer.echo("Please copy .env.example to .env and fill in your API keys.", err=True)
        raise typer.Exit(1)

    init_db()
    db = get_db_session()

    try:
        keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
        search_config = SearchConfig(subject=subject, subject_type=subject_type, keywords=keyword_list)
        searcher = VideoSearcher()

        typer.echo(f"🔍 Searching YouTube for: {subject} (type={subject_type})")
        videos = searcher.search(search_config, max_total_results=max_results)

        if fuzzy_dedup:
            videos = searcher.deduplicate_fuzzy(videos)

        typer.echo(f"📊 Found {len(videos)} unique videos. Scoring...")

        scorer = RelevanceScorer(ScoringConfig(subject=subject, subject_type=subject_type))
        videos = scorer.score_videos(videos)

        for video in videos:
            video.subject = subject
            video.subject_type = subject_type
            RightsClassifier.apply_to_video(video)

        repo = VideoRepository(db)
        for video in videos:
            repo.create_or_update(video)

        typer.echo(f"💾 Stored {len(videos)} videos in database.")
        typer.echo(f"🏆 Top video: {videos[0].title if videos else 'N/A'} (Score: {videos[0].relevance_score if videos else 0})")

    except Exception as e:
        logger.exception("Search failed")
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def analyze(
    subject: str = typer.Option(..., "--subject", "-s", help="Subject name or description"),
    subject_type: str = typer.Option("person", "--type", "-t", help="Subject type: person or scene"),
    max_videos: int = typer.Option(20, "--max-videos", help="Max videos to analyze"),
) -> None:
    """Fetch transcripts and analyze for interesting moments."""
    setup_logging()
    logger = logging.getLogger(__name__)

    if subject_type not in {"person", "scene"}:
        typer.echo(f"ERROR: --type must be 'person' or 'scene', got '{subject_type}'", err=True)
        raise typer.Exit(1)

    missing = Config.validate()
    if missing:
        typer.echo(f"ERROR: Missing configuration: {', '.join(missing)}", err=True)
        raise typer.Exit(1)

    init_db()
    db = get_db_session()

    try:
        video_repo = VideoRepository(db)
        transcript_repo = TranscriptRepository(db)
        moment_repo = MomentRepository(db)

        videos = video_repo.get_all(subject=subject, limit=max_videos)
        if not videos:
            typer.echo("No videos found. Run 'search' first.")
            raise typer.Exit(0)

        transcript_provider = YouTubeTranscriptProvider()
        llm_provider = get_llm_provider()
        analyzer = MomentAnalyzer(llm_provider)

        typer.echo(f"📝 Analyzing up to {len(videos)} videos for {subject}...")

        analyzed = 0
        for video in videos:
            existing = transcript_repo.get_by_video_id(video.video_id)
            if existing:
                logger.info("Transcript already exists for %s", video.video_id)
                transcript_text = existing.transcript
                from src.transcripts.base import TranscriptResult, TranscriptSegment
                transcript = TranscriptResult(
                    video_id=video.video_id,
                    segments=[TranscriptSegment(text=transcript_text, start=0.0, duration=0.0)],
                    language=existing.language,
                    source=existing.source,
                )
            else:
                transcript = transcript_provider.get_transcript(video.video_id)
                if transcript:
                    transcript_repo.save(
                        video.video_id,
                        transcript.timestamped_text,
                        language=transcript.language,
                        source=transcript.source,
                        timestamped=True,
                    )

            if not transcript:
                logger.info("Transcript unavailable for %s", video.video_id)
                continue

            try:
                moments = analyzer.analyze(transcript, subject, subject_type=subject_type)
                for moment in moments:
                    moment_repo.save(video.video_id, moment)
                analyzed += 1
                typer.echo(f"  ✓ {video.title[:60]}... ({len(moments)} moments)")
            except Exception as e:
                logger.error("Analysis failed for %s: %s", video.video_id, e)
                continue

        typer.echo(f"✅ Analyzed {analyzed} videos. Moments stored in database.")

    except RuntimeError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("Analysis failed")
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def report(
    subject: str = typer.Option(..., "--subject", "-s", help="Subject name or description"),
    format: str = typer.Option("all", "--format", "-f", help="Export format: all, markdown, csv, json"),
) -> None:
    """Generate research reports and exports."""
    setup_logging()
    init_db()
    db = get_db_session()

    try:
        base_name = slugify(subject)

        if format in ("all", "markdown"):
            md = MarkdownReport()
            path = md.generate(db, subject, filename=f"{base_name}_report.md")
            typer.echo(f"📄 Markdown report: {path}")

        if format in ("all", "csv"):
            csv_exp = CSVExporter()
            paths = csv_exp.export_all(db, subject)
            for key, path in paths.items():
                typer.echo(f"📊 CSV {key}: {path}")

        if format in ("all", "json"):
            json_exp = JSONExporter()
            paths = json_exp.export_all(db, subject)
            for key, path in paths.items():
                typer.echo(f"📋 JSON {key}: {path}")

    except Exception as e:
        logging.getLogger(__name__).exception("Report generation failed")
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command()
def build(
    subject: str = typer.Option(..., "--subject", "-s", help="Subject name or description"),
    min_score: int = typer.Option(5, "--min-score", help="Minimum interest score (0-10)"),
    max_clips: int = typer.Option(10, "--max-clips", help="Maximum number of clips to build"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory for clips"),
    include_rights_review: bool = typer.Option(False, "--include-rights-review", help="Include moments flagged for rights review"),
) -> None:
    """Download source videos and cut clips for each interesting moment."""
    setup_logging()
    logger = logging.getLogger(__name__)

    init_db()
    db = get_db_session()

    try:
        moment_repo = MomentRepository(db)
        moments = moment_repo.get_all(subject=subject)

        if not moments:
            typer.echo("No moments found. Run 'analyze' first.")
            raise typer.Exit(0)

        # Filter by minimum interest score
        moments = [m for m in moments if m.interest_score >= min_score]
        if not moments:
            typer.echo(f"No moments with interest score >= {min_score}. Try a lower --min-score.")
            raise typer.Exit(0)

        # Optionally exclude moments flagged for rights review
        if not include_rights_review:
            moments = [m for m in moments if not m.requires_rights_review]
            if not moments:
                typer.echo("All moments require rights review. Use --include-rights-review to proceed.")
                raise typer.Exit(0)

        # Sort by interest score descending and cap
        moments = sorted(moments, key=lambda m: m.interest_score, reverse=True)[:max_clips]

        typer.echo(f"🎬 Building {len(moments)} clip(s) for {subject}...")
        typer.echo(f"   Min score: {min_score}  |  Output: {output_dir}/")

        builder = VideoBuilder(output_dir=output_dir)
        results = builder.build_clips(moments, subject)

        success = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        for r in success:
            typer.echo(f"  ✓ {r.topic[:55]} ({r.duration}s) → {r.output_path}")
        for r in failed:
            typer.echo(f"  ✗ {r.topic[:55]} — {r.error}", err=True)

        typer.echo(f"\n✅ {len(success)}/{len(results)} clips built successfully.")
        if failed:
            typer.echo(f"⚠️  {len(failed)} clip(s) failed. Check logs for details.", err=True)

    except Exception as e:
        logger.exception("Build failed")
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.callback()
def callback() -> None:
    """YouTube Celebrity Interview Discovery & Clip Research Tool."""
    pass


if __name__ == "__main__":
    app()