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
from src.llm.openai_provider import OpenAIProvider
from src.rights.classifier import RightsClassifier
from src.scoring.relevance import RelevanceScorer, ScoringConfig
from src.transcripts.providers import YouTubeTranscriptProvider
from src.utils import slugify
from src.video.builder import VideoBuilder
from src.video.frames import extract_frames, cleanup_frames
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


def _analyze_video_frames(
    video_id: str,
    video_title: str,
    subject: str,
    subject_type: str,
    llm_provider,
    frame_interval: int,
    max_frames: int,
) -> list[dict]:
    """Analyze a video using frame extraction and image-to-text descriptions."""
    logger = logging.getLogger(__name__)

    # Extract frames
    frame_paths = extract_frames(
        video_id=video_id,
        interval_seconds=frame_interval,
        max_frames=max_frames,
    )

    if not frame_paths:
        logger.warning("No frames extracted for %s", video_id)
        return []

    # Use OpenAI for image description (only provider with vision support)
    vision_provider = OpenAIProvider()
    if not vision_provider.is_available():
        logger.error("OpenAI provider required for frame analysis but not available")
        cleanup_frames(frame_paths)
        return []

    # Get descriptions for each frame
    frame_descriptions = []
    for i, frame_path in enumerate(frame_paths):
        timestamp = i * frame_interval
        try:
            description = vision_provider.describe_image(
                image_url=f"file://{frame_path.absolute()}",
                prompt="Describe this video frame in detail. Focus on people, actions, text, objects, and setting.",
            )
            if description:
                frame_descriptions.append({
                    "timestamp": timestamp,
                    "description": description,
                })
        except Exception as e:
            logger.error("Failed to describe frame %d for %s: %s", i, video_id, e)

    # Clean up frame files
    cleanup_frames(frame_paths)

    if not frame_descriptions:
        logger.warning("No frame descriptions generated for %s", video_id)
        return []

    # Analyze frame descriptions using the main LLM provider
    try:
        moments = llm_provider.analyze_frames(frame_descriptions, subject, subject_type)
        return moments
    except Exception as e:
        logger.error("Frame analysis failed for %s: %s", video_id, e)
        return []


@app.command()
def analyze(
    subject: str = typer.Option(..., "--subject", "-s", help="Subject name or description"),
    subject_type: str = typer.Option("person", "--type", "-t", help="Subject type: person or scene"),
    max_videos: int = typer.Option(20, "--max-videos", help="Max videos to analyze"),
    use_frames: bool = typer.Option(False, "--use-frames", help="Fallback to frame-based analysis when transcript missing"),
    frame_interval: int = typer.Option(30, "--frame-interval", help="Seconds between frame extracts (default: 30)"),
    max_frames: int = typer.Option(10, "--max-frames", help="Max frames per video (default: 10)"),
) -> None:
    """Fetch transcripts and analyze for interesting moments. Falls back to frame analysis if enabled."""
    setup_logging()
    logger = logging.getLogger(__name__)

    if subject_type not in {"person", "scene"}:
        typer.echo(f"ERROR: --type must be 'person' or 'scene', got '{subject_type}'", err=True)
        raise typer.Exit(1)

    missing = Config.validate()
    if missing:
        typer.echo(f"ERROR: Missing configuration: {', '.join(missing)}", err=True)
        raise typer.Exit(1)

    if use_frames and not Config.IMAGE_TO_TEXT_ENABLED:
        typer.echo("ERROR: --use-frames requires IMAGE_TO_TEXT_ENABLED=true in config", err=True)
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
            # Try transcript first
            transcript = None
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

            moments = []
            if transcript:
                try:
                    moments = analyzer.analyze(transcript, subject, subject_type=subject_type)
                    typer.echo(f"  ✓ {video.title[:60]}... ({len(moments)} moments from transcript)")
                except Exception as e:
                    logger.error("Transcript analysis failed for %s: %s", video.video_id, e)
            elif use_frames and Config.IMAGE_TO_TEXT_ENABLED:
                # Fallback to frame-based analysis
                typer.echo(f"  ⏬ No transcript for {video.title[:60]}... extracting frames")
                moments = _analyze_video_frames(
                    video.video_id,
                    video.title,
                    subject,
                    subject_type,
                    llm_provider,
                    frame_interval,
                    max_frames,
                )
                if moments:
                    typer.echo(f"  ✓ {video.title[:60]}... ({len(moments)} moments from frames)")
                else:
                    typer.echo(f"  ✗ {video.title[:60]}... (no moments found from frames)")
            else:
                logger.info("Transcript unavailable for %s and frame fallback disabled", video.video_id)
                continue

            for moment in moments:
                moment_repo.save(video.video_id, moment)
            analyzed += 1

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


@app.command()
def run(
    subject: str = typer.Option(..., "--subject", "-s", help="Subject to search for (person or scene description)"),
    subject_type: str = typer.Option("person", "--type", "-t", help="Subject type: person or scene"),
    max_results: int = typer.Option(25, "--max-results", "-m", help="Maximum total search results"),
    max_videos: int = typer.Option(20, "--max-videos", help="Max videos to analyze"),
    use_frames: bool = typer.Option(True, "--use-frames/--no-frames", help="Enable frame-based fallback analysis"),
    frame_interval: int = typer.Option(30, "--frame-interval", help="Seconds between frame extracts"),
    max_frames: int = typer.Option(10, "--max-frames", help="Max frames per video"),
    min_score: int = typer.Option(5, "--min-score", help="Minimum interest score (0-10) for clips"),
    max_clips: int = typer.Option(10, "--max-clips", help="Maximum number of clips to build"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory for clips"),
    include_rights_review: bool = typer.Option(True, "--include-rights-review/--exclude-rights-review", help="Include moments flagged for rights review"),
) -> None:
    """Run the full pipeline: search → analyze → report → build."""
    # 1. Search
    typer.echo("🔎 Step 1/4: Searching YouTube...")
    search(
        subject=subject,
        subject_type=subject_type,
        keywords="",
        max_results=max_results,
        fuzzy_dedup=False,
    )
    # 2. Analyze
    typer.echo("\n🧠 Step 2/4: Analyzing transcripts/frames...")
    analyze(
        subject=subject,
        subject_type=subject_type,
        max_videos=max_videos,
        use_frames=use_frames,
        frame_interval=frame_interval,
        max_frames=max_frames,
    )
    # 3. Report
    typer.echo("\n📄 Step 3/4: Generating markdown report...")
    report(
        subject=subject,
        format="markdown",
    )
    # 4. Build
    typer.echo("\n🎬 Step 4/4: Building clips...")
    build(
        subject=subject,
        min_score=min_score,
        max_clips=max_clips,
        output_dir=output_dir,
        include_rights_review=include_rights_review,
    )
    typer.echo("\n✅ Pipeline completed.")


@app.callback()
def callback() -> None:
    """YouTube Celebrity Interview Discovery & Clip Research Tool."""
    pass


if __name__ == "__main__":
    app()