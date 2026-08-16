# YouTube Interview Discovery & Clip Research Tool

`ycid-crt` is a command-line tool for discovering YouTube videos about a person or scene, ranking the results, analyzing available transcripts for notable moments, exporting research reports, and—where you have the required rights—building source clips.

## Rights and permitted use

Finding a video on YouTube does **not** grant permission to reproduce, publish, or distribute it. The tool classifies available licensing metadata, but every discovered video and generated moment requires rights review.

The `build` command uses `yt-dlp` to download the selected time ranges from YouTube. Only use it for material you are authorized to download and reuse. You are responsible for obtaining any necessary permissions and complying with YouTube's terms and applicable law.

## What it does

- Searches YouTube through the YouTube Data API using generated or custom queries
- Supports `person` and `scene` subjects
- Deduplicates by video ID and can optionally apply fuzzy title deduplication
- Scores and stores results in a local SQLite database
- Retrieves available YouTube transcripts and uses an LLM to identify moments
- Exports Markdown, CSV, and JSON research outputs
- Builds timestamped clips from high-interest moments, with rights-review safeguards

## Requirements

- Python 3.13 or later
- A YouTube Data API key
- An LLM for `analyze`: OpenAI, Anthropic, or a running local Ollama instance
- `yt-dlp` on your `PATH` to use `build`
- Optional: `ffmpeg` for frame-accurate clip cuts

## Installation

```bash
git clone <repository-url>
cd rapidriver
uv sync
cp env.example .env
```

Edit `.env` and add at least your YouTube API key:

```dotenv
YOUTUBE_API_KEY=your_youtube_api_key_here
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
```

`LLM_PROVIDER` can be `openai`, `anthropic`, or `ollama`. For Ollama, start the local Ollama service and set `LLM_MODEL` to an installed model. The default database is `data/youtube_research.db`.

`yt-dlp` is installed into the project environment by `uv sync`. `ffmpeg` is recommended but not required:

```bash
brew install ffmpeg  # optional; macOS
```

## Quick start (full pipeline)

Run the entire pipeline—search → analyze → report → build—in one command:

```bash
uv run python main.py run --subject "Jennifer Aniston"
```

Defaults used by `run`:
- `max-results=25` (search)
- `max-videos=20` (analyze)
- `--use-frames` enabled (frame fallback when transcript missing)
- report format = **markdown**
- `--include-rights-review` enabled for clip building

Override any step with the corresponding flag, e.g.:

```bash
uv run python main.py run \
  --subject "Jennifer Aniston" \
  --max-results 50 \
  --max-videos 10 \
  --no-frames \
  --min-score 7 \
  --max-clips 5 \
  --output-dir clips \
  --exclude-rights-review
```

---

## Workflow

Run commands through the project environment with `uv run`.

### 1. Search for videos

Search for a person:

```bash
uv run python main.py search --subject "Jennifer Aniston"
```

Search for a scene or description:

```bash
uv run python main.py search \
  --subject "a chef preparing pasta in a restaurant kitchen" \
  --type scene
```

Provide your own comma-separated query keywords or change the result limit:

```bash
uv run python main.py search \
  --subject "Jennifer Aniston" \
  --keywords "interview,podcast,red carpet" \
  --max-results 100 \
  --fuzzy-dedup
```

The command fetches metadata, scores each result, classifies its available license metadata, and stores videos in the database.

### 2. Analyze transcripts

After searching, fetch available transcripts and identify noteworthy moments:

```bash
uv run python main.py analyze --subject "Jennifer Aniston"
```

Limit the number of stored videos processed or set the subject type explicitly:

```bash
uv run python main.py analyze \
  --subject "Jennifer Aniston" \
  --type person \
  --max-videos 10
```

Transcript text is retained in the local database. The analysis passes the first 15,000 characters of very long transcripts to the configured LLM. Detected moments are always marked for rights review.

### 3. Export research reports

Export every available format (the default):

```bash
uv run python main.py report --subject "Jennifer Aniston"
```

Or choose one format:

```bash
uv run python main.py report --subject "Jennifer Aniston" --format markdown
uv run python main.py report --subject "Jennifer Aniston" --format csv
uv run python main.py report --subject "Jennifer Aniston" --format json
```

Valid formats are `all`, `markdown`, `csv`, and `json`. Reports are written to `reports/` and filenames use a slug of the subject.

### 4. Build clips (only with permission)

`build` selects stored moments by interest score, excluding moments that require rights review by default:

```bash
uv run python main.py build --subject "Jennifer Aniston"
```

With explicit selection options:

```bash
uv run python main.py build \
  --subject "Jennifer Aniston" \
  --min-score 7 \
  --max-clips 5 \
  --output-dir clips
```

To include moments flagged for rights review, you must opt in explicitly:

```bash
uv run python main.py build \
  --subject "Jennifer Aniston" \
  --include-rights-review
```

Clips are saved below `<output-dir>/<subject-slug>/`. Without `ffmpeg`, cuts may start or end at a nearby keyframe rather than the exact requested timestamp.

## Configuration

All configuration is loaded from `.env` in the project root.

| Variable | Default | Purpose |
| --- | --- | --- |
| `YOUTUBE_API_KEY` | — | Required for search and analysis commands |
| `LLM_PROVIDER` | `openai` | `openai`, `anthropic`, or `ollama` |
| `LLM_MODEL` | `gpt-4o-mini` | Model name for the selected LLM provider |
| `OPENAI_API_KEY` | — | Required when using OpenAI |
| `ANTHROPIC_API_KEY` | — | Required when using Anthropic |
| `LLM_MAX_TOKENS` | `4000` | Maximum generated tokens for analysis |
| `LLM_TEMPERATURE` | `0.3` | LLM sampling temperature |
| `DATABASE_URL` | `sqlite:///data/youtube_research.db` | SQLAlchemy database URL |
| `MAX_SEARCH_RESULTS` | `50` | Default search-result limit configuration |
| `SEARCH_DELAY_SECONDS` | `1.0` | Delay between search requests |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Command reference

```text
uv run python main.py run     --subject TEXT [--type person|scene] [--max-results INT] [--max-videos INT] [--use-frames/--no-frames] [--frame-interval INT] [--max-frames INT] [--min-score INT] [--max-clips INT] [--output-dir PATH] [--include-rights-review/--exclude-rights-review]
uv run python main.py search  --subject TEXT [--type person|scene] [--keywords TEXT] [--max-results INT] [--fuzzy-dedup]
uv run python main.py analyze --subject TEXT [--type person|scene] [--max-videos INT] [--use-frames/--no-frames] [--frame-interval INT] [--max-frames INT]
uv run python main.py report  --subject TEXT [--format all|markdown|csv|json]
uv run python main.py build   --subject TEXT [--min-score INT] [--max-clips INT] [--output-dir PATH] [--include-rights-review/--exclude-rights-review]
```

Use `uv run python main.py <command> --help` for the full command help.
