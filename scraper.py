import os
import re
import instaloader
from datetime import datetime

SESSIONS_DIR = os.path.abspath("sessions")


def _session_file(username: str) -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return os.path.join(SESSIONS_DIR, f"session-{username}")


def extract_shortcode(url: str) -> str:
    match = re.search(r"/(?:p|reel|tv)/([^/?#&]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract shortcode from URL: {url}")


def create_loader_from_sessionid(sessionid: str) -> tuple[instaloader.Instaloader, str]:
    """Login using an Instagram session cookie. Returns (loader, username)."""
    L = instaloader.Instaloader(
        download_video_thumbnails=False,
        save_metadata=False,
        download_comments=False,
    )
    L.context._session.cookies.set("sessionid", sessionid, domain=".instagram.com")
    username = L.test_login()
    if not username:
        raise ValueError("Session cookie is invalid or expired.")
    # Persist so future password logins can reuse it
    try:
        L.save_session_to_file(_session_file(username))
    except Exception:
        pass
    return L, username


def create_loader_and_login(username: str, password: str) -> instaloader.Instaloader:
    L = instaloader.Instaloader(
        download_video_thumbnails=False,
        save_metadata=False,
        download_comments=False,
    )

    # Try reusing a saved session first — avoids re-auth and checkpoint triggers
    session_path = _session_file(username)
    if os.path.exists(session_path):
        try:
            L.load_session_from_file(username, session_path)
            print(f"Loaded saved session for {username}")
            return L
        except Exception as e:
            print(f"Saved session invalid, doing fresh login: {e}")

    # Fresh login
    L.login(username, password)

    # Persist session so future logins skip this step
    try:
        L.save_session_to_file(session_path)
        print(f"Session saved for {username}")
    except Exception as e:
        print(f"Could not save session: {e}")

    return L


def scrape_instagram_post(url: str, loader: instaloader.Instaloader) -> str:
    shortcode = extract_shortcode(url)

    base_raw = os.path.abspath("docs")
    folder_name = datetime.now().strftime("%d_%B_%Y")
    target_dir = os.path.join(base_raw, folder_name)
    os.makedirs(target_dir, exist_ok=True)

    loader.dirname_pattern = target_dir

    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
    except Exception as e:
        raise Exception(f"Failed to fetch post: {e}")

    print(f"Downloading post into {target_dir}...")
    loader.download_post(post, target=shortcode)
    print("Download complete.")

    return os.path.abspath(target_dir)
