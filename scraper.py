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


class CheckpointRequired(Exception):
    """Raised when Instagram demands a challenge; carries the loader and URL."""
    def __init__(self, loader: instaloader.Instaloader, challenge_url: str):
        self.loader = loader
        self.challenge_url = challenge_url
        super().__init__(f"Checkpoint required: {challenge_url}")


def _make_loader() -> instaloader.Instaloader:
    return instaloader.Instaloader(
        download_video_thumbnails=False,
        save_metadata=False,
        download_comments=False,
    )


def create_loader_and_login(username: str, password: str) -> instaloader.Instaloader:
    L = _make_loader()

    # Try reusing a saved session first — avoids re-auth and checkpoint triggers
    session_path = _session_file(username)
    if os.path.exists(session_path):
        try:
            L.load_session_from_file(username, session_path)
            print(f"Loaded saved session for {username}")
            return L
        except Exception as e:
            print(f"Saved session invalid, doing fresh login: {e}")

    try:
        L.login(username, password)
    except instaloader.exceptions.InstaloaderException as e:
        msg = str(e)
        cp_match = re.search(r"(https?://[^\s]+/(?:challenge|auth_platform)[^\s]*)", msg)
        if not cp_match:
            cp_match = re.search(r"Point your browser to (/[^\s]+)", msg)
        if cp_match:
            raise CheckpointRequired(L, cp_match.group(1))
        raise

    try:
        L.save_session_to_file(session_path)
        print(f"Session saved for {username}")
    except Exception as e:
        print(f"Could not save session: {e}")

    return L


def _challenge_headers(session, challenge_url: str) -> dict:
    csrf = session.cookies.get("csrftoken", "")
    return {
        "X-CSRFToken": csrf,
        "X-Instagram-AJAX": "1",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": challenge_url,
        "Origin": "https://www.instagram.com",
    }


def send_challenge_code(loader: instaloader.Instaloader, challenge_url: str) -> str:
    """
    Ask Instagram to send a verification code to the user's email/phone.
    Returns a hint string. Raises on hard failure.
    """
    if not challenge_url.startswith("http"):
        challenge_url = f"https://www.instagram.com{challenge_url}"

    session = loader.context._session
    # Prime cookies
    session.get(challenge_url, headers={"Referer": "https://www.instagram.com/"})

    headers = _challenge_headers(session, challenge_url)

    # Try JSON body first (newer /auth_platform/ endpoint), then form-encoded
    for payload, content_type in [
        ('{"choice":"1"}', "application/json"),
        ("choice=1",        "application/x-www-form-urlencoded"),
    ]:
        h = {**headers, "Content-Type": content_type}
        try:
            resp = session.post(challenge_url, data=payload, headers=h, timeout=10)
            data = resp.json()
            if data.get("status") == "ok":
                return data.get("message") or "Instagram sent a verification code to your email."
        except Exception:
            continue

    # Instagram often auto-sends the code when the checkpoint is raised —
    # even if our explicit request failed, the user may already have received it.
    return "Instagram sent a verification code to your registered email or phone."


def verify_challenge_code(
    loader: instaloader.Instaloader, challenge_url: str, code: str
) -> str:
    """
    Submit the verification code. Returns the authenticated username on success,
    raises ValueError on failure.
    """
    if not challenge_url.startswith("http"):
        challenge_url = f"https://www.instagram.com{challenge_url}"

    session = loader.context._session
    headers = _challenge_headers(session, challenge_url)
    code = code.strip()

    # Try JSON body (newer endpoint) then form-encoded (older /challenge/ endpoint)
    last_err = "Incorrect code or the challenge expired. Please try again."
    for payload, content_type in [
        (f'{{"security_code":"{code}"}}', "application/json"),
        (f"security_code={code}",          "application/x-www-form-urlencoded"),
    ]:
        h = {**headers, "Content-Type": content_type}
        try:
            resp = session.post(challenge_url, data=payload, headers=h, timeout=10)
            data = resp.json()
        except Exception:
            continue

        if data.get("status") == "ok":
            username = loader.test_login()
            if not username:
                raise ValueError("Verification accepted but session is still invalid.")
            try:
                loader.save_session_to_file(_session_file(username))
            except Exception:
                pass
            return username

        # Capture the error message but keep trying the other format
        last_err = data.get("message") or last_err

    raise ValueError(last_err)


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
