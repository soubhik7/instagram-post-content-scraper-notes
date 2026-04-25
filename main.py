from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, HttpUrl
import uvicorn
import os

from scraper import scrape_instagram_post
from doc_generator import generate_document

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Instagram Scraper Service", description="API to scrape Instagram posts and generate Word documents.")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse("static/index.html")

class ScrapeRequest(BaseModel):
    url: str

class ScrapeResponse(BaseModel):
    success: bool
    raw_directory: str
    document_path: str
    message: str

@app.post("/extract", response_model=ScrapeResponse)
def extract_post(request: ScrapeRequest):
    try:
        # Step 1: Scrape
        raw_dir = scrape_instagram_post(request.url)
        
        # Step 2: Generate Document
        doc_path = generate_document(raw_dir)
        
        return ScrapeResponse(
            success=True,
            raw_directory=raw_dir,
            document_path=doc_path,
            message="Successfully scraped post and generated document."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
