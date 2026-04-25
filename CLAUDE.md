# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload

# Test doc generator standalone
python doc_generator.py docs/<DD_Month_YYYY>/

# Docker
docker build -t smartdocs .
docker run -p 8000:8000 smartdocs
```

The API runs at `http://127.0.0.1:8000`. The UI is served at `/` from `static/index.html`.

## Architecture

Three-layer pipeline exposed as a FastAPI service with a two-screen browser UI.

### Auth flow
1. User enters Instagram credentials in the **login screen**.
2. `POST /login` calls `create_loader_and_login()` in `scraper.py`, which creates an `instaloader.Instaloader` instance and calls `.login()`.
3. The live loader object is stored in an in-memory dict (`_sessions`) keyed by a `secrets.token_urlsafe(32)` session ID. The ID is returned to the browser and kept only in JS memory.
4. Sessions expire after 2 hours; expired entries are purged lazily.

### Extract flow
1. `POST /extract` receives `{session_id, url}`, looks up the loader in `_sessions`, and calls `scrape_instagram_post(url, loader)`.
2. **Scrape** (`scraper.py`) — sets `loader.dirname_pattern` to `docs/<DD_Month_YYYY>/`, then calls `loader.download_post()`. Images and caption `.txt` land in that folder.
3. **Generate** (`doc_generator.py`) — reads the `.txt` and images, builds a styled A4 Word document, saves it as `Notes_<DD_Month_YYYY_HHMMAM/PM>.docx` (timestamp includes time to avoid same-day conflicts), then deletes all other files in the folder.
4. The docx path is stored in `_files` under a random `file_id` (expires after 1 hour). `{file_id, filename}` is returned to the browser.
5. `GET /download/{file_id}` streams the file as an attachment.

### UI (`static/index.html`)
Single HTML file, no build step. Two screens — `#loginScreen` and `#dashScreen` — swap visibility with CSS transitions. All state (session ID, file ID) lives in JS memory only.

## Output structure

```
docs/
  25_April_2026/
    Notes_25_April_2026_1015PM.docx   # final document (images + caption deleted after generation)
```

## Environment

`.env` is optional. If present, `INSTAGRAM_USERNAME` / `INSTAGRAM_PASSWORD` are used as fallback credentials when no UI login session exists (useful for local CLI testing). The file is gitignored.

```
INSTAGRAM_USERNAME=...
INSTAGRAM_PASSWORD=...
```

## Deployment

`render.yaml` defines a Docker web service on Render's free plan. Set `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD` as environment secrets in the Render dashboard (optional — UI sign-in works without them).

## Key design decisions

- **Credentials never stored** — only the authenticated `Instaloader` object lives in memory.
- **No path exposure** — the browser only ever sees opaque `file_id` tokens, not server paths.
- **In-memory sessions** — suitable for Render's single-instance free tier; would need Redis or similar for multi-instance deployments.
- **Lazy expiry purge** — `_purge_expired()` runs on every `/login`, `/extract`, and `/download` call; no background thread needed.
