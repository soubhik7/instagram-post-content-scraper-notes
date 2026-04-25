# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env  # then fill in INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD

# Run the server
uvicorn main:app --reload

# Test scraper or doc generator standalone
python scraper.py <instagram_post_url>
python doc_generator.py raw/<shortcode>
```

The API runs at `http://127.0.0.1:8000`. The UI is served at `/` from `static/index.html`.

## Architecture

This is a two-step pipeline exposed as a FastAPI service:

1. **Scrape** (`scraper.py`) — Uses `instaloader` to download a post's images and caption `.txt` into `raw/<shortcode>/`. Reads `INSTAGRAM_USERNAME` / `INSTAGRAM_PASSWORD` from `.env` via `python-dotenv`; falls back to unauthenticated (likely blocked by Instagram).

2. **Generate** (`doc_generator.py`) — Reads the `.txt` caption and sorted `.jpg`/`.png` images from the raw directory, then writes a `<shortcode>_combined.docx` into the same directory using `python-docx`.

3. **API** (`main.py`) — Single `POST /extract` endpoint accepts `{"url": "..."}`, chains the two steps above, and returns paths to the raw directory and `.docx`. Serves `static/index.html` as the frontend at `GET /`.

**Output structure:** `raw/<shortcode>/` contains the downloaded images, caption `.txt`, and the final `.docx`.

## Environment

Requires a `.env` file (not committed) with:
```
INSTAGRAM_USERNAME=...
INSTAGRAM_PASSWORD=...
```
