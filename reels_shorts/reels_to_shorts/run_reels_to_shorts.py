import inspect
import json
import logging
import os
import platform
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

import requests
from instagrapi import Client
from instagrapi.exceptions import LoginRequired
from dotenv import load_dotenv
from assets.youtube_upload import (
    upload_video,
    get_authenticated_service,
    UploadLimitExceeded,
)
from assets.youtube_token_desktop import generate_token as generate_token_desktop
from assets.youtube_token_headless import generate_token as generate_token_headless

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "app.log"


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
    fh = logging.FileHandler(LOG_FILE)
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

DOWNLOAD_DIR = BASE_DIR / "downloads"
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
CLIENT_SECRETS_FILE = BASE_DIR / "assets" / "token" / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"
IS_WINDOWS = platform.system().lower().startswith("win")
MAX_DOWNLOAD_WORKERS = min(8, max(2, (os.cpu_count() or 2)))
REQUEST_TIMEOUT = 10
CHUNK_SIZE = 1024 * 1024  # 1MB chunks for faster writes
REELS_TARGET = 20  # desired new downloads per run
# How many reels to request per API call; script keeps paging until it finds enough new ones.
REELS_BATCH_SIZE = int(os.getenv("REELS_BATCH_SIZE", 50))
SESSION = requests.Session()
PROCESSED_CACHE_FILE = BASE_DIR / "processed_reels.json"
SESSION_FILE = BASE_DIR / "session.json"
CAPTION_EMOJIS = ["🚀", "🔥", "✨", "💥", "🎯", "⭐️", "💫", "⚡️", "😎", "🙌"]


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


def load_processed_reels() -> Set[str]:
    """
    Return the set of media_pks already uploaded.
    """
    if not PROCESSED_CACHE_FILE.exists():
        return set()
    try:
        with open(PROCESSED_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(item) for item in data)
    except Exception as e:
        logger.warning(f"Failed to read {PROCESSED_CACHE_FILE}: {e}")
    return set()


def save_processed_reels(processed: Set[str]):
    """
    Persist the set of processed media_pks.
    """
    try:
        with open(PROCESSED_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(processed), f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {PROCESSED_CACHE_FILE}: {e}")


def _safe_client_call(method, params):
    try:
        return method(**params)
    except TypeError as e:
        try:
            allowed = inspect.signature(method).parameters
        except (TypeError, ValueError):
            raise e
        filtered = {key: value for key, value in params.items() if key in allowed}
        if filtered == params:
            raise e
        return method(**filtered)


def _is_reel_media(media) -> bool:
    product_type = getattr(media, "product_type", None)
    if product_type:
        return product_type == "clips"
    media_type = getattr(media, "media_type", None)
    return str(media_type) == "2"


def resolve_source_user_id(client) -> Tuple[Optional[str], Optional[str]]:
    source_username = os.getenv("INSTAGRAM_SOURCE_USERNAME") or INSTAGRAM_USERNAME
    if source_username:
        try:
            return str(client.user_id_from_username(source_username)), source_username
        except Exception as e:
            logger.warning(
                f"Failed to resolve user id for @{source_username}: {e}. Falling back to authenticated user."
            )

    user_id = getattr(client, "user_id", None)
    if user_id:
        username = getattr(client, "username", None) or source_username
        if not username:
            try:
                info = client.account_info()
                username = getattr(info, "username", None)
            except Exception:
                username = None
        if username:
            logger.info(f"Using authenticated user @{username} as reel source.")
        else:
            logger.info("Using authenticated user id as reel source.")
        return str(user_id), username

    return None, source_username


def resolve_reels_method(client, source_user_id: Optional[str]):
    if source_user_id:
        for method_name in ("user_clips", "user_clips_v1"):
            method = getattr(client, method_name, None)
            if callable(method):
                return method_name, method
        method = getattr(client, "user_medias", None)
        if callable(method):
            return "user_medias", method
    method = getattr(client, "reels", None)
    if callable(method):
        return "reels", method
    return None, None


def build_reel_tasks(
    client,
    processed_ids: Set[str],
    source_user_id: Optional[str],
    source_username: Optional[str],
) -> List[ReelDownloadTask]:
    """
    Fetch reel metadata and build download tasks.
    """
    tasks: List[ReelDownloadTask] = []
    skipped_existing = 0
    skipped_processed = 0
    seen_pks = set()
    last_media_pk = 0
    batch = 0
    use_pagination = False

    method_name, method = resolve_reels_method(client, source_user_id)
    if not method:
        logger.error("No supported Instagram reel source method available.")
        return []

    if method_name in ("user_clips", "user_clips_v1", "user_medias"):
        target = f"@{source_username}" if source_username else "the target account"
        logger.info(f"Fetching reels for {target} via {method_name}...")
    else:
        logger.info("Fetching reels from the reels feed...")
        use_pagination = True

    while len(tasks) < REELS_TARGET:
        try:
            params = {"amount": REELS_BATCH_SIZE}
            if method_name in ("user_clips", "user_clips_v1", "user_medias"):
                user_id_value = int(source_user_id) if source_user_id and source_user_id.isdigit() else source_user_id
                params["user_id"] = user_id_value
            if use_pagination and last_media_pk:
                params["last_media_pk"] = last_media_pk
            reels = _safe_client_call(method, params)
            if method_name == "user_medias":
                reels = [media for media in reels or [] if _is_reel_media(media)]
        except Exception as e:
            logger.error(f"Error fetching reels (batch {batch + 1}): {e}")
            break

        if not reels:
            if batch == 0:
                if method_name in ("user_clips", "user_clips_v1", "user_medias") and source_username:
                    logger.warning(f"No reels found for @{source_username}.")
                else:
                    logger.warning("No reels found.")
            else:
                logger.info("No more reels returned by Instagram; stopping.")
            break

        batch += 1
        logger.info(f"Fetched {len(reels)} reels (batch {batch}). Preparing download tasks...")

        new_seen_this_batch = 0
        for reel in reels:
            media_pk = getattr(reel, "pk", None) or getattr(reel, "id", None)
            if not media_pk:
                logger.warning("Skipping reel with no media id/pk")
                continue

            if media_pk in seen_pks:
                continue
            seen_pks.add(media_pk)
            new_seen_this_batch += 1

            if use_pagination:
                try:
                    last_media_pk = int(str(media_pk))
                except Exception:
                    pass

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
            output_path = str(DOWNLOAD_DIR / output_filename)

            if str(media_pk) in processed_ids:
                skipped_processed += 1
                continue

            if os.path.exists(output_path):
                skipped_existing += 1
                continue

            tasks.append(
                ReelDownloadTask(
                    order=len(tasks),
                    media_pk=str(media_pk),
                    video_url=video_url,
                    output_path=output_path,
                )
            )

            if len(tasks) >= REELS_TARGET:
                break

        if len(tasks) >= REELS_TARGET:
            break
        if not use_pagination:
            break

        if new_seen_this_batch == 0:
            logger.info("No new reels beyond what was already processed; stopping pagination.")
            break

    if skipped_existing:
        logger.info(f"Skipped {skipped_existing} already-downloaded reel(s).")
    if skipped_processed:
        logger.info(f"Skipped {skipped_processed} already-uploaded reel(s) from cache.")
    return tasks


def process_reels(client, processed_ids: Set[str]) -> List[Tuple[str, str]]:
    """
    Build download tasks and fetch reels concurrently.
    Returns list of (media_pk, path) for successfully downloaded files.
    """
    logger.info("Processing reels...")

    source_user_id, source_username = resolve_source_user_id(client)
    tasks = build_reel_tasks(client, processed_ids, source_user_id, source_username)
    if not tasks:
        return []

    downloaded: List[Tuple[int, str, str]] = []
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
                downloaded.append((task.order, task.media_pk, output_path))

    downloaded.sort(key=lambda item: item[0])
    logger.info(f"Downloaded {len(downloaded)} reel(s).")
    return [(pk, path) for _, pk, path in downloaded]


def ensure_youtube_token():
    """
    Ensure token.json exists; generate it with the right OAuth flow per platform.
    """
    if TOKEN_FILE.exists():
        return

    logger.info(f"{TOKEN_FILE} not found. Generating a new token...")
    try:
        if IS_WINDOWS:
            logger.info("Launching desktop OAuth flow for YouTube...")
            generate_token_desktop(str(CLIENT_SECRETS_FILE), str(TOKEN_FILE))
        else:
            logger.info("Launching headless OAuth flow for YouTube...")
            generate_token_headless(str(CLIENT_SECRETS_FILE), str(TOKEN_FILE))
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
        if SESSION_FILE.exists():
            client.load_settings(str(SESSION_FILE))
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        else:
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            client.dump_settings(str(SESSION_FILE))
        logger.info("Logged in to Instagram successfully.")
        return client
    except LoginRequired:
        logger.error("Session expired. Re-attempting login.")
        try:
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            client.dump_settings(str(SESSION_FILE))
            return client
        except Exception as e:
            logger.error(f"Re-login failed: {e}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Login failed: {e}")
        sys.exit(1)


def main():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    processed_ids = load_processed_reels()
    if processed_ids:
        logger.info(f"Loaded {len(processed_ids)} processed reel(s) from cache.")

    client = login_instagram()

    ensure_youtube_token()

    downloaded = process_reels(client, processed_ids)
    if not downloaded:
        logger.warning("No new downloads this run; nothing to upload.")
        return

    try:
        youtube = get_authenticated_service(token_file=str(TOKEN_FILE))
    except Exception as e:
        logger.error(f"Error creating YouTube client: {e}")
        return

    uploads_succeeded = 0
    for media_pk, video_path in downloaded:
        emoji = random.choice(CAPTION_EMOJIS) if CAPTION_EMOJIS else "✨"
        tags = "#shorts #reels #viral #subscribe"
        title = f"Subscribe {emoji}"
        description = f"Subscribe for more {emoji}\n\n{tags}"

        logger.info(f"Uploading: {os.path.basename(video_path)} (media {media_pk})")
        try:
            upload_video(youtube, video_path, title, description, category_id=22, privacy_status="public")
            uploads_succeeded += 1
            processed_ids.add(str(media_pk))
            save_processed_reels(processed_ids)
            try:
                os.remove(video_path)
                logger.info(f"Deleted uploaded file {video_path} to save space.")
            except OSError as cleanup_err:
                logger.warning(f"Uploaded but could not delete {video_path}: {cleanup_err}")
        except UploadLimitExceeded:
            logger.error("YouTube upload limit exceeded; stopping remaining uploads.")
            break
        except Exception as e:
            logger.error(f"Failed to upload {video_path}: {e}")

    logger.info(f"All tasks completed. Uploaded {uploads_succeeded} new reel(s).")


if __name__ == "__main__":
    main()
