import os
import secrets
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

import instaloader
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scraper import create_loader_and_login, scrape_instagram_post
from doc_generator import generate_document

app = FastAPI(title="SmartDocs")

os.makedirs("static", exist_ok=True)
os.makedirs("docs", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# In-memory session + file store (single-process; fine for Render free tier)
# ---------------------------------------------------------------------------

SESSION_TTL = timedelta(hours=2)
FILE_TTL = timedelta(hours=1)

_lock = threading.Lock()

# session_id -> {loader, username, expires_at}
_sessions: Dict[str, dict] = {}

# file_id -> {path, expires_at}
_files: Dict[str, dict] = {}


def _purge_expired():
    now = datetime.utcnow()
    with _lock:
        expired_s = [k for k, v in _sessions.items() if v["expires_at"] < now]
        for k in expired_s:
            del _sessions[k]
        expired_f = [k for k, v in _files.items() if v["expires_at"] < now]
        for k in expired_f:
            del _files[k]


def _get_session(session_id: str) -> dict:
    _purge_expired()
    with _lock:
        session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    return session


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    session_id: str
    username: str

class ExtractRequest(BaseModel):
    session_id: str
    url: str

class ExtractResponse(BaseModel):
    file_id: str
    filename: str

class LogoutRequest(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse("static/index.html")


@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if not req.username.strip() or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    try:
        loader = create_loader_and_login(req.username.strip(), req.password)
    except instaloader.exceptions.BadCredentialsException:
        raise HTTPException(status_code=401, detail="Invalid Instagram username or password.")
    except instaloader.exceptions.InstaloaderException as e:
        raise HTTPException(status_code=502, detail=f"Instagram login error: {e}")

    session_id = secrets.token_urlsafe(32)
    with _lock:
        _sessions[session_id] = {
            "loader": loader,
            "username": req.username.strip(),
            "expires_at": datetime.utcnow() + SESSION_TTL,
        }
    return LoginResponse(session_id=session_id, username=req.username.strip())


@app.post("/logout")
def logout(req: LogoutRequest):
    with _lock:
        _sessions.pop(req.session_id, None)
    return {"ok": True}


@app.post("/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest):
    session = _get_session(req.session_id)
    loader: instaloader.Instaloader = session["loader"]

    try:
        raw_dir = scrape_instagram_post(req.url, loader)
        doc_path = generate_document(raw_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    file_id = secrets.token_urlsafe(24)
    filename = os.path.basename(doc_path)
    with _lock:
        _files[file_id] = {
            "path": doc_path,
            "filename": filename,
            "expires_at": datetime.utcnow() + FILE_TTL,
        }
    return ExtractResponse(file_id=file_id, filename=filename)


@app.get("/download/{file_id}")
def download(file_id: str):
    _purge_expired()
    with _lock:
        entry = _files.get(file_id)
    if not entry:
        raise HTTPException(status_code=404, detail="File not found or link expired.")
    if not os.path.exists(entry["path"]):
        raise HTTPException(status_code=404, detail="File no longer available on disk.")
    return FileResponse(
        path=entry["path"],
        filename=entry["filename"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{entry["filename"]}"'},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
