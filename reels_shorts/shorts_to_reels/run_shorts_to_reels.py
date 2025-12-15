import os
import sys
import subprocess
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Tuple, List

import requests
from instagrapi import Client
import yt_dlp as youtube_dl
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
    search_url = f"https://www.youtube.com/results?search_query={query}&sp=EgkSB3lvdXR1YmUu"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/85.0.4183.102'
    }
    try:
        response = SESSION.get(search_url, headers=headers, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logger.error(f"Request for YouTube Shorts failed: {e}")
        return []
    video_urls = []

    if response.status_code == 200:
        page_content = response.text
        video_ids = set()
        while len(video_ids) < max_results:
            index = page_content.find('/shorts/')
            if index == -1:
                break
            video_id = page_content[index + 8:index + 19]
            if video_id:
                video_ids.add(video_id)
            page_content = page_content[index + 19:]

        for video_id in video_ids:
            video_urls.append(f"https://www.youtube.com/shorts/{video_id}")
    else:
        logger.error(f"Failed to fetch YouTube Shorts page. Status code: {response.status_code}")
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
        'concurrent_fragment_downloads': CONCURRENT_FRAGMENT_DOWNLOADS,
        'retries': 3,
        'merge_output_format': 'mp4',
    }

    # Try a preferred mp4-first format, then fall back to best available.
    formats_to_try = [
        'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/bv*+ba/best',
        'best'
    ]

    for fmt in formats_to_try:
        ydl_opts = dict(base_opts)
        ydl_opts['format'] = fmt
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([video_url])
                logger.info(f"Downloaded video to: {output_path} (format: {fmt})")
                return output_path
            except Exception as e:
                logger.error(f"Failed to download video {video_id} with format '{fmt}': {e}")

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


def adjust_aspect_ratio_ffmpeg(video_path, target_width=1080, target_height=1920):
    """
    Adjusts the video's aspect ratio to 9:16 using FFmpeg.
    Crops and resizes the video to fit the target aspect ratio and resolution.
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

        (
            ffmpeg
            .input(video_path)
            .filter('scale', scale_width, scale_height)
            .filter('crop', target_width, target_height, x_crop, y_crop)
            .output(
                output_path,
                vcodec='libx264',
                acodec='aac',
                pix_fmt='yuv420p',
                video_bitrate='5M',
                audio_bitrate='128k',
                strict='experimental'
            )
            .overwrite_output()
            .run(quiet=True)
        )

        logger.info(f"Adjusted video saved to {output_path}")
        return output_path, (target_width, target_height)
    except Exception as e:
        logger.error(f"Failed to adjust aspect ratio for {video_path}: {e}")
        return video_path, get_video_dimensions(video_path)


def post_to_instagram(client, video_path, caption, dimensions=None):
    """
    Uploads a video to Instagram with the given caption.
    """
    try:
        if not is_valid_video(video_path):
            logger.error(f"Video {video_path} is invalid or corrupted. Skipping upload.")
            return

        width, height = dimensions if dimensions else get_video_dimensions(video_path)
        if width and height:
            aspect = width / height
            logger.info(f"Uploading video {video_path} ({width}x{height}, aspect ratio {aspect:.4f})")

        media = client.clip_upload(video_path, caption)
        logger.info(f"Posted reel to Instagram with caption: '{caption}'")

        time.sleep(60)
    except Exception as e:
        logger.error(f"Failed to post to Instagram: {e}")


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
    logger.info(f"\nProcessing YouTube Short #{order + 1}: {video_url}")
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
    youtube_videos = get_youtube_shorts(query, max_videos)
    if not youtube_videos:
        logger.error("No YouTube Shorts found for the provided query.")
        sys.exit(1)

    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    client = login_instagram()

    caption = 'Your caption'  # Replace with your desired caption

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
        post_to_instagram(client, prepared.path, caption, prepared.dimensions)

    logger.info("\nAll tasks completed.")


if __name__ == "__main__":
    main()
