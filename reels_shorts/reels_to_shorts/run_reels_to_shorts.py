import os
import sys
import platform
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Optional

import requests
from instagrapi import Client
from instagrapi.exceptions import LoginRequired
from dotenv import load_dotenv
from assets.youtube_upload import upload_all_videos_in_folder, get_authenticated_service
from assets.youtube_token_desktop import generate_token as generate_token_desktop
from assets.youtube_token_headless import generate_token as generate_token_headless


class ColorFormatter(logging.Formatter):
    COLORS = {
        "INFO": "\033[92m",      # green
        "WARNING": "\033[93m",   # yellow
        "ERROR": "\033[91m",     # red
        "RESET": "\033[0m",
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"]
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


def configure_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # File handler (detailed)
    fh = logging.FileHandler("app.log")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(message)s'))

    # Console handler (concise, colored)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColorFormatter('%(levelname)s - %(message)s'))

    logger.handlers = []
    logger.addHandler(fh)
    logger.addHandler(ch)

    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("instagrapi").setLevel(logging.WARNING)

    return logger


logger = configure_logging()

load_dotenv()

DOWNLOAD_PATH = os.path.join('downloads')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
CLIENT_SECRETS_FILE = "./assets/token/client_secrets.json"
TOKEN_FILE = "token.json"
IS_WINDOWS = platform.system().lower().startswith("win")
MAX_DOWNLOAD_WORKERS = min(8, max(2, (os.cpu_count() or 2)))
REQUEST_TIMEOUT = 10
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for faster writes
REELS_TARGET = 20  # desired new downloads per run
REELS_FETCH_SIZE = REELS_TARGET * 3  # grab more to skip already-downloaded
SESSION = requests.Session()


@dataclass
class ReelDownloadTask:
    order: int
    media_pk: str
    video_url: str
    output_path: str


def download_instagram_video(task: ReelDownloadTask) -> Optional[str]:
    """
    Downloads an Instagram video using a prepared task.
    """
    try:
        response = SESSION.get(task.video_url, stream=True, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        with open(task.output_path, 'wb') as video_file:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    video_file.write(chunk)

        logger.info(f"Downloaded video to: {task.output_path}")
        return task.output_path

    except Exception as e:
        logger.error(f"Failed to download video for media ID {task.media_pk}: {e}")
        return None


def build_reel_tasks(client, amount: int = REELS_FETCH_LIMIT) -> List[ReelDownloadTask]:
    """
    Fetch reel metadata and build download tasks.
    """
    try:
        reels = client.reels(amount=REELS_FETCH_SIZE)
    except Exception as e:
        logger.error(f"Error fetching reels: {e}")
        return []

    if not reels:
        logger.warning("No reels found.")
        return []

    tasks: List[ReelDownloadTask] = []
    skipped_existing = 0
    logger.info(f"Found {len(reels)} reels. Preparing download tasks...")
    for idx, reel in enumerate(reels):
        media_pk = getattr(reel, "pk", None) or getattr(reel, "id", None)
        if not media_pk:
            logger.warning("Skipping reel with no media id/pk")
            continue

        video_url = getattr(reel, "video_url", None)
        if not video_url:
            try:
                media_info = client.media_info(media_pk)
                video_url = getattr(media_info, "video_url", None)
            except Exception as e:
                logger.error(f"Failed to fetch video URL for media {media_pk}: {e}")
                continue

        if not video_url:
            logger.warning(f"No video URL found for media ID: {media_pk}")
            continue

        output_filename = f"{media_pk}.mp4"
        output_path = os.path.join(DOWNLOAD_PATH, output_filename)

        if os.path.exists(output_path):
            skipped_existing += 1
            continue

        tasks.append(
            ReelDownloadTask(
                order=idx,
                media_pk=str(media_pk),
                video_url=video_url,
                output_path=output_path,
            )
        )
        if len(tasks) >= REELS_TARGET:
            break

    if skipped_existing:
        logger.info(f"Skipped {skipped_existing} already-downloaded reel(s).")
    return tasks


def process_reels(client) -> List[str]:
    """
    Build download tasks and fetch reels concurrently.
    """
    logger.info("Processing reels...")

    tasks = build_reel_tasks(client, amount=REELS_FETCH_LIMIT)
    if not tasks:
        return []

    downloaded = []
    with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS, thread_name_prefix="reel-dl") as executor:
        futures = {executor.submit(download_instagram_video, task): task for task in tasks}
        for future in as_completed(futures):
            task = futures[future]
            try:
                output_path = future.result()
            except Exception as e:
                logger.error(f"Error downloading reel {task.media_pk}: {e}")
                continue

            if output_path:
                downloaded.append((task.order, output_path))

    downloaded.sort(key=lambda item: item[0])
    logger.info(f"Downloaded {len(downloaded)} reel(s).")
    return [path for _, path in downloaded]


def ensure_youtube_token():
    """
    Ensure token.json exists; generate it with the right OAuth flow per platform.
    """
    if os.path.exists(TOKEN_FILE):
        return

    logger.info(f"{TOKEN_FILE} not found. Generating a new token...")
    try:
        if IS_WINDOWS:
            logger.info("Launching desktop OAuth flow for YouTube...")
            generate_token_desktop(CLIENT_SECRETS_FILE, TOKEN_FILE)
        else:
            logger.info("Launching headless OAuth flow for YouTube...")
            generate_token_headless(CLIENT_SECRETS_FILE, TOKEN_FILE)
        logger.info(f"Token generated and saved to {TOKEN_FILE}.")
    except Exception as e:
        logger.error(f"Failed to generate token: {e}")
        sys.exit(1)


def login_instagram():
    """
    Login with session reuse; abort if credentials missing.
    """
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        logger.error("INSTAGRAM_USERNAME/PASSWORD not set in environment.")
        sys.exit(1)

    client = Client()
    try:
        if os.path.exists("session.json"):
            client.load_settings("session.json")
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        else:
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            client.dump_settings("session.json")
        logger.info("Logged in to Instagram successfully.")
        return client
    except LoginRequired:
        logger.error("Session expired. Re-attempting login.")
        try:
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            client.dump_settings("session.json")
            return client
        except Exception as e:
            logger.error(f"Re-login failed: {e}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Login failed: {e}")
        sys.exit(1)


def main():
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    client = login_instagram()

    ensure_youtube_token()

    downloaded_paths = process_reels(client)
    if not downloaded_paths:
        logger.warning("No new downloads this run; will upload any existing files in downloads.")

    try:
        youtube = get_authenticated_service()
        upload_all_videos_in_folder(youtube, DOWNLOAD_PATH)
    except Exception as e:
        logger.error(f"Error uploading videos to YouTube: {e}")

    logger.info("All tasks completed.")


if __name__ == "__main__":
    main()
