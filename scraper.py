import os
import re
import instaloader
from datetime import datetime


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
    L.login(username, password)
    return L


def scrape_instagram_post(url: str, loader: instaloader.Instaloader) -> str:
    shortcode = extract_shortcode(url)

    base_raw = os.path.abspath("docs")
    folder_name = datetime.now().strftime("%d_%B_%Y")
    target_dir = os.path.join(base_raw, folder_name)
    os.makedirs(target_dir, exist_ok=True)

    # Override dirname_pattern so files land in the dated folder
    loader.dirname_pattern = target_dir

    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
    except Exception as e:
        raise Exception(f"Failed to fetch post: {e}")

    print(f"Downloading post into {target_dir}...")
    loader.download_post(post, target=shortcode)
    print("Download complete.")

    return os.path.abspath(target_dir)
