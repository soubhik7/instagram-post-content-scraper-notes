# TechNotes — SmartDocs

Turn Instagram posts into clean, downloadable Word documents. Sign in with your Instagram account through the browser UI, paste a post URL, and download a formatted `.docx` in one click.

## Features

- Browser-based Instagram sign-in — credentials never stored on the server
- Secure per-request session tokens (expire after 2 hours)
- Direct `.docx` download from the browser (no server paths exposed)
- Documents named with date + time to avoid same-day conflicts: `Notes_25_April_2026_1015PM.docx`
- Outputs saved to `docs/<DD_Month_YYYY>/`
- Docker-ready, deployable to Render with one click

## Prerequisites

- Python 3.11+ **or** Docker
- An Instagram account

## Local Development

### Without Docker

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. (Optional) Set fallback credentials via .env
cp .env.template .env   # fill in INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD

# 4. Start the server
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

### With Docker

```bash
docker build -t smartdocs .
docker run -p 8000:8000 smartdocs
```

## Usage

1. Open the app in your browser.
2. Enter your Instagram **username** and **password** and click **Sign In**. The credentials are sent to the server once to authenticate with Instagram; they are never stored on disk.
3. Paste an Instagram post URL (e.g. `https://www.instagram.com/p/CzK2hPuvs_9/`).
4. Click **Extract & Generate Doc**.
5. Click **Download .docx** — the file is streamed directly to your browser.

## API Reference

### `POST /login`
Authenticate with Instagram and start a session.

**Request**
```json
{ "username": "your_ig_handle", "password": "your_password" }
```
**Response**
```json
{ "session_id": "<token>", "username": "your_ig_handle" }
```

### `POST /extract`
Scrape a post and generate a Word document.

**Request**
```json
{ "session_id": "<token>", "url": "https://www.instagram.com/p/…" }
```
**Response**
```json
{ "file_id": "<token>", "filename": "Notes_25_April_2026_1015PM.docx" }
```

### `GET /download/{file_id}`
Download the generated `.docx`. Links expire after 1 hour.

### `POST /logout`
Invalidate the session.

**Request**
```json
{ "session_id": "<token>" }
```

## Deployment on Render

1. Push this repository to GitHub.
2. Go to [render.com](https://render.com) → **New** → **Blueprint** → connect your repo.  
   Render reads `render.yaml` automatically.
3. In the Render dashboard, set the environment variables:
   - `INSTAGRAM_USERNAME` — optional fallback (UI sign-in takes priority)
   - `INSTAGRAM_PASSWORD` — optional fallback

## Project Structure

```
smartdocs/
├── main.py             # FastAPI app — login, extract, download endpoints
├── scraper.py          # instaloader wrapper; accepts a live Instaloader session
├── doc_generator.py    # python-docx document builder
├── static/
│   └── index.html      # Single-page UI (login + dashboard screens)
├── docs/               # Output folder — gitignored
├── Dockerfile
├── render.yaml
└── requirements.txt
```

## Security Notes

- Session IDs and file IDs are generated with `secrets.token_urlsafe(32)`.
- Sessions expire after **2 hours**; file download links expire after **1 hour**.
- Expired entries are purged automatically on each request.
- Credentials are used once to call `instaloader.login()` and are not retained.
- The `docs/` output folder and `.env` file are gitignored.
