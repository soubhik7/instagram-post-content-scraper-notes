import os
import re
import secrets
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

import instaloader
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scraper import create_loader_and_login, scrape_instagram_post, create_fb_session, scrape_facebook_post
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

# session_id -> {loader, username, expires_at}          (Instagram)
_sessions: Dict[str, dict] = {}

# fb_session_id -> {username, cookie_file, expires_at}  (Facebook)
_fb_sessions: Dict[str, dict] = {}

# file_id -> {path, expires_at}
_files: Dict[str, dict] = {}


def _purge_expired():
    now = datetime.utcnow()
    with _lock:
        for store in (_sessions, _fb_sessions, _files):
            for k in [k for k, v in store.items() if v["expires_at"] < now]:
                del store[k]


def _get_session(session_id: str) -> dict:
    _purge_expired()
    with _lock:
        session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    return session


def _get_fb_session(fb_session_id: str) -> dict:
    _purge_expired()
    with _lock:
        session = _fb_sessions.get(fb_session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Facebook session expired or invalid. Please log in again.")
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

class CheckpointError(BaseModel):
    checkpoint_url: str

class ExtractRequest(BaseModel):
    session_id: str
    url: str

class ExtractResponse(BaseModel):
    file_id: str
    filename: str

class LogoutRequest(BaseModel):
    session_id: str

class LoginFbRequest(BaseModel):
    username: str
    password: str

class LoginFbResponse(BaseModel):
    fb_session_id: str
    username: str

class ExtractFbRequest(BaseModel):
    fb_session_id: str
    url: str

class LogoutFbRequest(BaseModel):
    fb_session_id: str


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
        msg = str(e)
        # Extract checkpoint URL if present and return it as a distinct error code
        # so the UI can render it as a clickable link
        cp_match = re.search(r"(https?://[^\s]+/auth_platform/[^\s]*)", msg)
        if not cp_match:
            cp_match = re.search(r"Point your browser to (/[^\s]+)", msg)
        if cp_match:
            raise HTTPException(
                status_code=409,
                detail={"type": "checkpoint", "url": cp_match.group(1)},
            )
        raise HTTPException(status_code=502, detail=f"Instagram login error: {msg}")

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


@app.post("/login-fb", response_model=LoginFbResponse)
def login_fb(req: LoginFbRequest):
    if not req.username.strip() or not req.password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    try:
        fb_session = create_fb_session(req.username.strip(), req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Facebook login error: {e}")

    fb_session_id = secrets.token_urlsafe(32)
    with _lock:
        _fb_sessions[fb_session_id] = {
            **fb_session,
            "expires_at": datetime.utcnow() + SESSION_TTL,
        }
    return LoginFbResponse(fb_session_id=fb_session_id, username=req.username.strip())


@app.post("/logout-fb")
def logout_fb(req: LogoutFbRequest):
    with _lock:
        _fb_sessions.pop(req.fb_session_id, None)
    return {"ok": True}


@app.post("/extract-fb", response_model=ExtractResponse)
def extract_fb(req: ExtractFbRequest):
    fb_session = _get_fb_session(req.fb_session_id)
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL is required.")
    try:
        raw_dir = scrape_facebook_post(req.url.strip(), fb_session)
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
