# Instagram Post Content Scraper Service

This service automatically scrapes an Instagram post to extract its images and text content, saves them locally in a `raw/` directory, and compiles them into a `.docx` Word document.

## Prerequisites

- Python 3.9+
- An Instagram account

## Installation

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. **Provide Instagram Credentials:**
   Copy `.env.template` to `.env` and fill in your Instagram username and password. This is mandatory because Instagram strictly blocks unauthenticated scraping.
   ```bash
   cp .env.template .env
   # Edit .env with your credentials
   ```

## Usage

### Run Service
1. Start the API using Uvicorn:
   ```bash
   uvicorn main:app --reload
   ```
2. The service will be running at `http://127.0.0.1:8000`.

### Make a Request
Send a POST request to `/extract` with an Instagram post URL:
```bash
curl -X POST "http://127.0.0.1:8000/extract" \
     -H "Content-Type: application/json" \
     -d '{"url":"https://www.instagram.com/p/CzK2hPuvs_9/"}'
```

### Response
The response will indicate success and provide the absolute paths of the created files:
```json
{
  "success": true,
  "raw_directory": "/path/to/smartdocs/raw/CzK2hPuvs_9",
  "document_path": "/path/to/smartdocs/raw/CzK2hPuvs_9/CzK2hPuvs_9_combined.docx",
  "message": "Successfully scraped post and generated document."
}
```

## Structure
- `scraper.py`: Core logic for fetching post data using `instaloader`.
- `doc_generator.py`: Generates the `.docx` document by compiling the locally saved images and captions using `python-docx`.
- `main.py`: The FastAPI application for the web service.
- `raw/`: Folder where post contents and final documents are saved.
# instagram-post-content-scraper-notes
