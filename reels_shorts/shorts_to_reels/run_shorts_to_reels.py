import os
import sys
import subprocess
import logging
import time
import re
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Tuple, List

import requests
from instagrapi import Client
import yt_dlp as youtube_dl
from yt_dlp.version import __version__ as ytdlp_version
from dotenv import load_dotenv
import ffmpeg


class ColorFormatter(logging.Formatter):
    COLORS = {
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
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

    fh = logging.FileHandler("app.log")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(message)s'))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColorFormatter('%(levelname)s - %(message)s'))

    logger.handlers = []
    logger.addHandler(fh)
    logger.addHandler(ch)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("instagrapi").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.ERROR)

    return logger


logger = configure_logging()

load_dotenv()

DOWNLOAD_PATH = os.path.join('downloads')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
MAX_WORKERS = min(8, max(2, (os.cpu_count() or 2)))
REQUEST_TIMEOUT = 10
FFPROBE_TIMEOUT = 30
CONCURRENT_FRAGMENT_DOWNLOADS = min(4, MAX_WORKERS)
SESSION = requests.Session()
PROCESSED_CACHE_FILE = "processed_shorts.json"
CAPTION_EMOJIS = ["🚀", "🔥", "✨", "💥", "🎯", "⭐️", "💫", "⚡️", "😎", "🙌"]
MIN_YTDLP_VERSION = "2025.12.8"


class YTDlpLogger:
    """
    Silence yt_dlp progress spam while still surfacing warnings/errors.
    """
    _once_tokens = set()

    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def debug(self, msg):
        # Progress messages come through debug; swallow them to avoid UI spam.
        if isinstance(msg, str) and msg.startswith("[download]"):
            return

    def warning(self, msg):
        # Ignore noisy yt_dlp nsig/android fallback warnings that don't affect success.
        if not isinstance(msg, str):
            self._logger.warning(msg)
            return

        lowered = msg.lower()
        if "nsig extraction failed" in lowered or "falling back to generic n function search" in lowered:
            return

        # The new yt-dlp releases log an informational warning about missing JS runtimes.
        if "javascript runtime" in lowered:
            token = "js-runtime"
            if token not in self._once_tokens:
                self._once_tokens.add(token)
                self._logger.info(msg)
            return

        # SABR streaming warnings are benign for Shorts downloads; drop them.
        if "sabr streaming" in lowered:
            return

        self._logger.warning(msg)

    def error(self, msg):
        if isinstance(msg, str) and "Requested format is not available" in msg:
            self._logger.warning(msg)
            return
        self._logger.error(msg)


def compact_exception(exc: Exception) -> str:
    """
    Return a short, single-line description of an exception.
    """
    text = str(exc).strip()
    if not text:
        return exc.__class__.__name__
    return text.split("\n", 1)[0]


def _version_tuple(ver_str: str) -> Tuple[int, ...]:
    """
    Convert a version string like '2025.12.8' into a tuple of ints for comparison.
    """
    parts = re.findall(r"\d+", ver_str)
    return tuple(int(p) for p in parts) if parts else (0,)


def ensure_ytdlp_version():
    """
    Bail out early if yt-dlp is too old to fetch Shorts reliably.
    """
    current = _version_tuple(ytdlp_version)
    minimum = _version_tuple(MIN_YTDLP_VERSION)
    if current < minimum:
        logger.error(
            f"yt-dlp {ytdlp_version} is too old and will fail on Shorts (HTTP 403 / missing formats). "
            f"Please upgrade to >= {MIN_YTDLP_VERSION}: pip install -U yt-dlp"
        )
        sys.exit(1)


ensure_ytdlp_version()


@dataclass
class PreparedVideo:
    order: int
    video_url: str
    path: str
    dimensions: Optional[Tuple[int, int]] = None


def get_video_dimensions(video_path):
    """
    Returns video width and height using ffprobe.
    """
    try:
        probe = ffmpeg.probe(video_path, select_streams='v:0')
        video_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        return int(video_info['width']), int(video_info['height'])
    except Exception as e:
        logger.error(f"Unable to read dimensions for {video_path}: {e}")
        return None, None


def has_audio_stream(video_path) -> bool:
    """
    Check if the file contains an audio stream.
    """
    try:
        probe = ffmpeg.probe(video_path)
        return any(stream.get("codec_type") == "audio" for stream in probe.get("streams", []))
    except Exception as e:
        logger.error(f"Unable to read audio info for {video_path}: {e}")
        return False


def describe_audio_stream(video_path) -> str:
    """
    Return a short description of the first audio stream, or 'none'.
    """
    try:
        probe = ffmpeg.probe(video_path)
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "audio":
                codec = stream.get("codec_name", "unknown")
                channels = stream.get("channels", "?")
                return f"{codec} ({channels} ch)"
        return "none"
    except Exception:
        return "unknown"


def extract_video_id(video_url):
    """
    Extracts the YouTube video ID from a given URL.
    """
    from urllib.parse import urlparse, parse_qs
    parsed_url = urlparse(video_url)
    if parsed_url.path.startswith('/shorts/'):
        return parsed_url.path.split('/shorts/')[1].split('?')[0]
    query = parse_qs(parsed_url.query)
    return query.get('v', [None])[0]


def get_youtube_shorts(query, max_results=5):
    """
    Retrieves YouTube Shorts URLs based on a search query.
    """
    from urllib.parse import quote_plus

    encoded_query = quote_plus(query)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgkSB3lvdXR1YmUu"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/85.0.4183.102',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        response = SESSION.get(search_url, headers=headers, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logger.error(f"Request for YouTube Shorts failed: {e}")
        return []
    video_urls = []

    if response.status_code == 200:
        page_content = response.text
        seen_ids = set()
        matches = re.findall(r'/shorts/([a-zA-Z0-9_-]{11})', page_content)
        for video_id in matches:
            if video_id in seen_ids:
                continue
            video_urls.append(f"https://www.youtube.com/shorts/{video_id}")
            seen_ids.add(video_id)
            if len(video_urls) >= max_results:
                break
    else:
        logger.error(f"Failed to fetch YouTube Shorts page. Status code: {response.status_code}")

    if video_urls:
        logger.info(f"Found {len(video_urls)} shorts via HTML scrape.")
        return video_urls

    logger.warning("No shorts found via HTML scrape; falling back to yt_dlp search.")
    return search_shorts_with_yt_dlp(query, max_results)


def search_shorts_with_yt_dlp(query, max_results=5):
    """
    Fallback: use yt_dlp's search to fetch short videos (<= 90s) when HTML scraping fails.
    """
    video_urls = []
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',
        'default_search': 'ytsearch',
        'noplaylist': True,
    }

    try:
        search_term = f"ytsearch{max_results * 3}:{query}"
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_term, download=False)
    except Exception as e:
        logger.error(f"yt_dlp search failed: {e}")
        return video_urls

    entries = result.get('entries', []) if result else []
    seen_ids = set()
    for entry in entries:
        video_id = entry.get('id') or extract_video_id(entry.get('url', ''))
        if not video_id or video_id in seen_ids:
            continue
        if entry.get('is_live'):
            continue

        duration = entry.get('duration')
        if duration is not None and duration > 90:
            continue

        seen_ids.add(video_id)
        video_urls.append(f"https://www.youtube.com/shorts/{video_id}")
        if len(video_urls) >= max_results:
            break

    logger.info(f"yt_dlp fallback found {len(video_urls)} video(s).")
    return video_urls


def download_youtube_video(video_url):
    """
    Downloads a YouTube Short video if it hasn't been downloaded already.
    """
    video_id = extract_video_id(video_url)
    if not video_id:
        logger.error(f"Failed to extract video ID from URL: {video_url}")
        return None

    output_filename = f"{video_id}.mp4"
    output_path = os.path.join(DOWNLOAD_PATH, output_filename)

    if os.path.exists(output_path):
        logger.info(f"Video {video_id} has already been downloaded. Skipping download.")
        return output_path

    base_opts = {
        'outtmpl': output_path,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        },
        'quiet': True,
        'no_warnings': True,
        'verbose': False,
        'noprogress': True,
        'progress_with_newline': False,
        'concurrent_fragment_downloads': CONCURRENT_FRAGMENT_DOWNLOADS,
        'retries': 3,
        'merge_output_format': 'mp4',
        'logger': YTDlpLogger(),
        'noplaylist': True,
        'postprocessors': [
            {
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': 'mp4'
            }
        ],
    }

    # Try a preferred mp4-first format, then fall back to best available.
    formats_to_try = [
        # Broad catch-all: best video+audio merged, remux to mp4 after.
        'bv*+ba/bestvideo+bestaudio/best',
        # Prefer a progressive mp4 with both audio+video to guarantee sound.
        'best[ext=mp4][acodec!=none][vcodec!=none]/best[height<=1080][acodec!=none]/best[acodec!=none]',
        # DASH video+audio capped at 1080p with m4a audio when possible.
        'bv*[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best',
        # Generic DASH video+audio capped at 1080p.
        'bv*[ext=mp4][height<=1080]+ba/bestvideo[ext=mp4][height<=1080]+bestaudio/best[ext=mp4]/best',
        # Ultra-safe legacy mp4 format.
        '18/best'
    ]

    errors = []
    for fmt in formats_to_try:
        ydl_opts = dict(base_opts)
        ydl_opts['format'] = fmt
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([video_url])
                # Confirm audio is present; if not, retry with next format.
                if not has_audio_stream(output_path):
                    logger.warning(f"Downloaded {output_path} with no audio; retrying with next format.")
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except OSError:
                            pass
                    continue
                audio_desc = describe_audio_stream(output_path)
                logger.info(f"Downloaded video to: {output_path} (format: {fmt}, audio: {audio_desc})")
                return output_path
            except Exception as e:
                short_error = compact_exception(e)
                errors.append(f"{fmt}: {short_error}")
                # Clean up any partial file so later retries can succeed.
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except OSError:
                        pass
                logger.warning(f"Download attempt for {video_id} using '{fmt}' failed: {short_error}")

    if errors:
        joined = "; ".join(errors)
        logger.error(f"Failed to download video {video_id}. Tried formats -> {joined}")
    return None



def is_valid_video(video_path):
    """
    Validates that the video file is not corrupted and has a duration greater than 0.
    Uses FFmpeg to probe the video.
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=FFPROBE_TIMEOUT
        )
        duration = float(result.stdout.strip())
        if duration > 0:
            logger.info(f"Video {video_path} is valid with duration {duration} seconds.")
            return True
        logger.error(f"Video {video_path} has invalid duration: {duration} seconds.")
        return False
    except Exception as e:
        logger.error(f"Validation failed for {video_path}: {e}")
        return False


def load_processed_shorts():
    """
    Load already-processed YouTube IDs to avoid reprocessing.
    """
    if not os.path.exists(PROCESSED_CACHE_FILE):
        return set()
    try:
        with open(PROCESSED_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(item) for item in data)
    except Exception as e:
        logger.warning(f"Failed to read {PROCESSED_CACHE_FILE}: {e}")
    return set()


def save_processed_shorts(processed_ids):
    """
    Persist processed YouTube IDs.
    """
    try:
        with open(PROCESSED_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(processed_ids), f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {PROCESSED_CACHE_FILE}: {e}")


def adjust_aspect_ratio_ffmpeg(video_path, target_width=1080, target_height=1920):
    """
    Adjusts the video's aspect ratio to 9:16 using FFmpeg.
    Crops and resizes the video to fit the target aspect ratio and resolution, preserving audio when present.
    """
    logger.info(f"Adjusting aspect ratio for {video_path}")

    output_filename = f"adjusted_{os.path.basename(video_path)}"
    output_path = os.path.join(DOWNLOAD_PATH, output_filename)

    if os.path.exists(output_path):
        logger.info(f"Adjusted file already exists for {video_path}. Skipping re-render.")
        return output_path, get_video_dimensions(output_path)

    try:
        orig_width, orig_height = get_video_dimensions(video_path)
        if not orig_width or not orig_height:
            return video_path, None

        target_aspect = target_width / target_height
        orig_aspect = orig_width / orig_height

        if orig_aspect > target_aspect:
            scale_height = target_height
            scale_width = int(scale_height * orig_aspect)
        else:
            scale_width = target_width
            scale_height = int(scale_width / orig_aspect)

        if scale_width % 2:
            scale_width += 1
        if scale_height % 2:
            scale_height += 1

        x_crop = (scale_width - target_width) // 2
        y_crop = (scale_height - target_height) // 2

        src = ffmpeg.input(video_path)
        video = src.video.filter('scale', scale_width, scale_height).filter('crop', target_width, target_height, x_crop, y_crop)
        audio = getattr(src, "audio", None)

        # If audio exists, include it; otherwise render video only.
        if audio is not None:
            stream = ffmpeg.output(
                video,
                audio,
                output_path,
                vcodec='libx264',
                acodec='aac',
                pix_fmt='yuv420p',
                video_bitrate='5M',
                audio_bitrate='128k',
                strict='experimental'
            )
        else:
            stream = ffmpeg.output(
                video,
                output_path,
                vcodec='libx264',
                pix_fmt='yuv420p',
                video_bitrate='5M',
                strict='experimental'
            )

        stream = stream.overwrite_output()
        ffmpeg.run(stream, quiet=True)

        logger.info(f"Adjusted video saved to {output_path}")
        return output_path, (target_width, target_height)
    except Exception as e:
        logger.error(f"Failed to adjust aspect ratio for {video_path}: {e}")
        return video_path, get_video_dimensions(video_path)


def post_to_instagram(client, video_path, caption, dimensions=None):
    """
    Uploads a video to Instagram with the given caption.
    Returns True on success.
    """
    try:
        if not is_valid_video(video_path):
            logger.error(f"Video {video_path} is invalid or corrupted. Skipping upload.")
            return False

        width, height = dimensions if dimensions else get_video_dimensions(video_path)
        if width and height:
            aspect = width / height
            logger.info(f"Uploading video {video_path} ({width}x{height}, aspect ratio {aspect:.4f})")

        media = client.clip_upload(video_path, caption)
        logger.info(f"Posted reel to Instagram with caption: '{caption}'")

        time.sleep(60)
        return True
    except Exception as e:
        logger.error(f"Failed to post to Instagram: {e}")
        return False


def cleanup_files(adjusted_path: str):
    """
    Delete adjusted and original files to avoid storage bloat.
    """
    candidates = [adjusted_path]
    basename = os.path.basename(adjusted_path)
    if basename.startswith("adjusted_"):
        orig = os.path.join(os.path.dirname(adjusted_path), basename.replace("adjusted_", "", 1))
        candidates.append(orig)
    for path in candidates:
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Deleted local file {path} after upload.")
            except OSError as e:
                logger.warning(f"Uploaded but could not delete {path}: {e}")


def login_instagram():
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
    except Exception as e:
        logger.error(f"Login failed: {e}")
        sys.exit(1)


def prepare_video(order: int, video_url: str) -> Optional[PreparedVideo]:
    """
    Download, validate, and adjust a single video. Runs safely in threads.
    """
    logger.info(f"Processing YouTube Short #{order + 1}: {video_url}")
    output_path = download_youtube_video(video_url)
    if not output_path:
        return None

    if not is_valid_video(output_path):
        logger.error(f"Downloaded video {output_path} is invalid or corrupted. Re-downloading.")
        output_path = download_youtube_video(video_url)
        if not output_path or not is_valid_video(output_path):
            logger.error(f"Failed to obtain a valid video for {video_url}. Skipping.")
            return None

    adjusted_video_path, dimensions = adjust_aspect_ratio_ffmpeg(output_path)
    return PreparedVideo(order=order, video_url=video_url, path=adjusted_video_path, dimensions=dimensions)


def main():
    if len(sys.argv) != 2:
        logger.error("Usage: python run_shorts_to_reels.py <query>")
        sys.exit(1)
    query = sys.argv[1]
    max_videos = 5
    processed_ids = load_processed_shorts()
    if processed_ids:
        logger.info(f"Loaded {len(processed_ids)} processed short(s) from cache.")

    youtube_videos = get_youtube_shorts(query, max_videos * 2)
    if not youtube_videos:
        logger.error("No YouTube Shorts found for the provided query.")
        sys.exit(1)

    # Filter out already processed shorts
    pre_filter_count = len(youtube_videos)
    youtube_videos = [
        url for url in youtube_videos
        if extract_video_id(url) not in processed_ids
    ]
    if pre_filter_count != len(youtube_videos):
        logger.info(f"Skipped {pre_filter_count - len(youtube_videos)} already-uploaded short(s) from cache.")
    youtube_videos = youtube_videos[:max_videos]
    if not youtube_videos:
        logger.warning("No new shorts to process after filtering cached uploads.")
        return

    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    client = login_instagram()

    emoji = random.choice(CAPTION_EMOJIS) if CAPTION_EMOJIS else "✨"
    caption = f"Subscribe {emoji}"

    prepared_videos: List[PreparedVideo] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="worker") as executor:
        futures = {
            executor.submit(prepare_video, idx, video_url): (idx, video_url)
            for idx, video_url in enumerate(youtube_videos[:max_videos])
        }
        for future in as_completed(futures):
            idx, video_url = futures[future]
            try:
                prepared = future.result()
            except Exception as e:
                logger.error(f"Error processing {video_url}: {e}")
                continue
            if prepared:
                prepared_videos.append(prepared)

    prepared_videos.sort(key=lambda item: item.order)

    for prepared in prepared_videos:
        logger.info(f"Posting video to Instagram with caption: '{caption}' from {prepared.video_url}")
        uploaded = post_to_instagram(client, prepared.path, caption, prepared.dimensions)
        if uploaded:
            vid_id = extract_video_id(prepared.video_url)
            processed_ids.add(vid_id)
            save_processed_shorts(processed_ids)
            cleanup_files(prepared.path)

    logger.info("All tasks completed.")


if __name__ == "__main__":
    main()
