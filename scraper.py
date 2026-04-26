import os
import re
import instaloader
import yt_dlp
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

SESSIONS_DIR = os.path.abspath("sessions")


def _session_file(username: str) -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return os.path.join(SESSIONS_DIR, f"session-{username}")


def extract_shortcode(url: str) -> str:
    match = re.search(r"/(?:p|reel|tv)/([^/?#&]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract shortcode from URL: {url}")


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


FB_COOKIES_DIR = os.path.join(SESSIONS_DIR, "fb")


def fb_cookie_file(username: str) -> str:
    os.makedirs(FB_COOKIES_DIR, exist_ok=True)
    return os.path.join(FB_COOKIES_DIR, f"cookies-{username}.txt")


def _write_netscape_cookies(path: str, cookies: list) -> None:
    """Write Playwright cookies to a Netscape-format cookie file for yt-dlp."""
    lines = ["# Netscape HTTP Cookie File\n"]
    for c in cookies:
        domain = c.get("domain", "")
        flag   = "TRUE" if domain.startswith(".") else "FALSE"
        path_  = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        expiry = str(int(c.get("expires", 0))) if c.get("expires") and c["expires"] > 0 else "0"
        name   = c.get("name", "")
        value  = c.get("value", "")
        lines.append(f"{domain}\t{flag}\t{path_}\t{secure}\t{expiry}\t{name}\t{value}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def create_fb_session(username: str, password: str) -> dict:
    """
    Log in to Facebook using a real headless browser (Playwright), export the
    resulting session cookies to a Netscape cookie file, then return a session
    dict that scrape_facebook_post can use with yt-dlp.
    """
    cookie_path = fb_cookie_file(username)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx  = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = ctx.new_page()

        try:
            page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=30000)
            page.fill("#email", username)
            page.fill("#pass",  password)
            page.click("[name='login']")

            # Wait for navigation away from the login page
            try:
                page.wait_for_url(
                    lambda url: "login" not in url and "checkpoint" not in url,
                    timeout=15000,
                )
            except PlaywrightTimeout:
                current = page.url
                if "login" in current:
                    raise ValueError("Invalid Facebook email/username or password.")
                if "checkpoint" in current:
                    raise ValueError(
                        "Facebook security check required. Please log in via a browser first, "
                        "complete any security prompts, then try again."
                    )

            # Confirm we're actually logged in
            if "login" in page.url:
                raise ValueError("Invalid Facebook email/username or password.")

            cookies = ctx.cookies()
            _write_netscape_cookies(cookie_path, cookies)
        finally:
            browser.close()

    return {"username": username, "cookie_file": cookie_path}


def scrape_facebook_post(url: str, fb_session: dict) -> str:
    folder_name = datetime.now().strftime("%d_%B_%Y")
    target_dir = os.path.join(os.path.abspath("docs"), folder_name)
    os.makedirs(target_dir, exist_ok=True)

    ydl_opts = {
        "outtmpl": os.path.join(target_dir, "%(id)s.%(ext)s"),
        "cookiefile": fb_session["cookie_file"],
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if info is None:
        raise Exception("Could not extract post data from Facebook URL.")

    # Playlists = albums with multiple photos; single entries = one photo/video
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        description = next(
            (e.get("description") for e in entries if e and e.get("description")),
            "",
        ) or ""
    else:
        description = info.get("description") or info.get("title") or ""

    txt_path = os.path.join(target_dir, "caption.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(description.strip() or "(No caption found)")

    return os.path.abspath(target_dir)
