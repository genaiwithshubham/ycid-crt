# YouTube Celebrity Interview Discovery & Clip Research Tool(YCID-CRT)

A production-quality Python application for discovering, organizing, ranking, and analyzing publicly available YouTube interviews and clips related to celebrities.

## ⚠️ Important Copyright Notice

**Finding a video on YouTube does NOT grant you rights to reproduce, publish, or distribute it.**

This tool is designed for **research and discovery only**. It helps you:

- Discover relevant videos
- Collect metadata
- Identify potentially interesting moments
- Analyze available transcripts/captions where permitted
- Track licensing/rights information
- Prepare candidate moments for **human review**

You must obtain proper rights or permission before reusing any footage. This application does not download, copy, or republish videos.

## Features

- **YouTube Data API integration** — Official API usage only, no scraping
- **Multi-query search** — Automatically generates search variants
- **Deduplication** — By video ID and optional fuzzy title matching
- **Relevance scoring** — Configurable scoring system
- **Rights classification** — Tracks license status with appropriate warnings
- **Transcript analysis** — Abstracted provider interface (YouTube captions, files, manual)
- **LLM-powered moment detection** — OpenAI and Anthropic support
- **Multiple export formats** — CSV, JSON, Markdown reports, and clip manifests
- **SQLite database** — Local storage, no external infrastructure needed

## Requirements

- Python 3.11+
- YouTube Data API key
- OpenAI or Anthropic API key (for transcript analysis)

## Installation

```bash
git clone &lt;repository&gt;
cd youtube-celebrity-research
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Search

`python main.py search --celebrity "Jennifer Aniston"`

with options

```bash
python main.py search \
  --celebrity "Jennifer Aniston" \
  --keywords "interview,podcast,red carpet" \
  --max-results 100 \
  --fuzzy-dedup
```

This will:

1. Generate multiple search queries
2. Fetch video metadata via YouTube Data API
3. Deduplicate results
4. Score videos by relevance
5. Store everything in data/youtube_research.db

## Analyze

`python main.py analyze --celebrity "Jennifer Aniston"`

This will:

1. Fetch available transcripts/captions
2. Send transcripts to the configured LLM
3. Identify interesting moments
4. Store moments in the database

## Report

`python main.py report --celebrity "Jennifer Aniston"`

```bash
python main.py report --celebrity "Jennifer Aniston" --format markdown
python main.py report --celebrity "Jennifer Aniston" --format csv
python main.py report --celebrity "Jennifer Aniston" --format json
```

## Video

```bash
# After search + analyze:
python main.py build --celebrity "Jennifer Aniston"

# With options:
python main.py build -c "Jennifer Aniston" --min-score 7 --max-clips 5 -o clips/
python main.py build -c "Jennifer Aniston" --include-rights-review
```

## Project Structure

youtube-celebrity-research/
├── main.py                  # CLI entry point
├── requirements.txt
├── .env.example
├── .gitignore
├── src/
│   ├── config.py
│   ├── youtube/
│   │   ├── client.py        # YouTube Data API client
│   │   ├── search.py        # Search orchestration
│   │   └── models.py        # Video & search config models
│   ├── database/
│   │   ├── database.py      # SQLAlchemy engine
│   │   ├── models.py        # ORM models
│   │   └── repository.py    # CRUD operations
│   ├── scoring/
│   │   └── relevance.py     # Configurable scoring
│   ├── rights/
│   │   └── classifier.py    # License classification
│   ├── transcripts/
│   │   ├── base.py          # Abstract provider
│   │   └── providers.py     # YouTube & file providers
│   ├── llm/
│   │   ├── base.py          # Abstract LLM
│   │   ├── openai_provider.py
│   │   └── anthropic_provider.py
│   ├── analysis/
│   │   └── moments.py       # Moment detection
│   └── export/
│       ├── csv_export.py
│       ├── json_export.py
│       └── markdown_report.py
└── tests/
    ├── test_search.py
    ├── test_scoring.py
    ├── test_rights.py
    └── test_analysis.py

`pytest tests/ -v`

## Contributing

TBD
