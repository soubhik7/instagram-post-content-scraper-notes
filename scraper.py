import os
import re
import instaloader
from dotenv import load_dotenv

load_dotenv()

def extract_shortcode(url: str) -> str:
    """Extracts the Instagram shortcode from a URL."""
    # Matches patterns like /p/SHORTCODE/ or /reels/SHORTCODE/
    match = re.search(r"/(?:p|reel|tv)/([^/?#&]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract shortcode from URL: {url}")

def scrape_instagram_post(url: str) -> str:
    """
    Scrapes the Instagram post and saves resources into raw/<shortcode>.
    Returns the absolute path to the targeted raw directory.
    """
    shortcode = extract_shortcode(url)
    
    # Configure Instaloader
    L = instaloader.Instaloader(
        download_video_thumbnails=False,
        save_metadata=False,
        download_comments=False
    )
    
    # Login if credentials are provided in environment
    username = os.environ.get("INSTAGRAM_USERNAME")
    password = os.environ.get("INSTAGRAM_PASSWORD")
    
    if username and password:
        try:
            L.login(username, password)
            print(f"Logged in successfully as {username}")
        except instaloader.exceptions.InstaloaderException as e:
            print(f"Login failed: {e}. Attempting unauthenticated request...")
    else:
        print("No INSTAGRAM_USERNAME or INSTAGRAM_PASSWORD found. Trying without login.")
        
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
    except Exception as e:
        raise Exception(f"Failed to fetch post: {e}")
        
    target_dir = os.path.join("raw", shortcode)
    
    # Ensure raw directory exists
    os.makedirs(target_dir, exist_ok=True)
    
    # Download post into the target directory
    print(f"Downloading post into {target_dir}...")
    L.download_post(post, target=target_dir)
    print("Download complete.")
    
    return os.path.abspath(target_dir)

if __name__ == "__main__":
    # Test script locally
    import sys
    if len(sys.argv) > 1:
        scrape_instagram_post(sys.argv[1])
    else:
        print("Usage: python scraper.py <instagram_post_url>")
