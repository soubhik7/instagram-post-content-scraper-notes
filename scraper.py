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

    L.login(username, password)

    try:
        L.save_session_to_file(session_path)
        print(f"Session saved for {username}")
    except Exception as e:
        print(f"Could not save session: {e}")

    return L


def send_challenge_code(loader: instaloader.Instaloader, challenge_url: str) -> str:
    """
    Ask Instagram to send a verification code to the user's email/phone.
    Returns a human-readable description of where the code was sent.
    """
    if not challenge_url.startswith("http"):
        challenge_url = f"https://www.instagram.com{challenge_url}"

    session = loader.context._session
    # Fetch the challenge page to prime cookies / get CSRF
    session.get(challenge_url, headers={"Referer": "https://www.instagram.com/"})
    csrf = session.cookies.get("csrftoken", "")

    # choice=1 → email, choice=0 → SMS (fall back to 1 if only email available)
    resp = session.post(
        challenge_url,
        data={"choice": "1"},
        headers={
            "X-CSRFToken": csrf,
            "Referer": challenge_url,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        data = resp.json()
    except Exception:
        data = {}

    if data.get("status") == "ok":
        return data.get("message", "Code sent to your email.")
    # Fallback: still tell user to check — code may have been auto-sent
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
    csrf = session.cookies.get("csrftoken", "")

    resp = session.post(
        challenge_url,
        data={"security_code": code.strip()},
        headers={
            "X-CSRFToken": csrf,
            "Referer": challenge_url,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        data = resp.json()
    except Exception:
        data = {}

    if data.get("status") != "ok":
        raise ValueError(data.get("message", "Incorrect code. Please try again."))

    # Confirm the session is now authenticated
    username = loader.test_login()
    if not username:
        raise ValueError("Verification succeeded but session is still invalid.")

    try:
        loader.save_session_to_file(_session_file(username))
    except Exception:
        pass

    return username


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
