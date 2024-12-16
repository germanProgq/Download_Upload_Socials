import os
import subprocess
import requests
from moviepy.editor import VideoFileClip
from instagrapi import Client
import yt_dlp as youtube_dl
import tempfile
from PIL import Image
from dotenv import load_dotenv
import sys
import logging
import ffmpeg
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

DOWNLOAD_PATH = os.path.join('downloads')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
    }
    response = requests.get(search_url, headers=headers)
    video_urls = []

    if response.status_code == 200:
        page_content = response.text
        video_ids = set()
        while len(video_ids) < max_results:
            index = page_content.find('/shorts/')
            if index == -1:
                break
            video_id = page_content[index+8:index+19]
            if video_id:
                video_ids.add(video_id)
            page_content = page_content[index+19:]

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

    # Check if the video has already been downloaded
    if os.path.exists(output_path):
        logger.info(f"Video {video_id} has already been downloaded. Skipping download.")
        return output_path

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        },
        'quiet': True,  # Set to False for debugging
        'no_warnings': True,
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([video_url])
            logger.info(f"Downloaded video to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to download video {video_id}: {e}")
            return None

    return output_path

def is_valid_video(video_path):
    """
    Validates that the video file is not corrupted and has a duration greater than 0.
    Uses FFmpeg to probe the video.
    """
    try:
        # Run FFmpeg to probe the video
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        duration = float(result.stdout.strip())
        if duration > 0:
            logger.info(f"Video {video_path} is valid with duration {duration} seconds.")
            return True
        else:
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

    try:
        # Build the FFmpeg filter complex
        # First, scale the video while maintaining aspect ratio
        # Then, crop to the desired aspect ratio
        # Finally, set the output resolution

        # Get original dimensions
        probe = ffmpeg.probe(video_path)
        video_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        orig_width = int(video_info['width'])
        orig_height = int(video_info['height'])

        target_aspect = target_width / target_height
        orig_aspect = orig_width / orig_height

        if orig_aspect > target_aspect:
            # Video is wider than target aspect ratio
            new_width = int(target_aspect * orig_height)
            x_crop = (orig_width - new_width) // 2
            y_crop = 0
            crop_filter = f"crop={new_width}:{orig_height}:{x_crop}:{y_crop}"
        else:
            # Video is taller than target aspect ratio
            new_height = int(orig_width / target_aspect)
            x_crop = 0
            y_crop = (orig_height - new_height) // 2
            crop_filter = f"crop={orig_width}:{new_height}:{x_crop}:{y_crop}"

        # Build FFmpeg command
        (
            ffmpeg
            .input(video_path)
            .filter('crop', new_width=new_width if orig_aspect > target_aspect else orig_width,
                    new_height=orig_height if orig_aspect > target_aspect else new_height,
                    x=x_crop, y=y_crop)
            .filter('scale', width=target_width, height=target_height)
            .output(output_path, codec='libx264', audio_codec='aac', strict='experimental')
            .overwrite_output()
            .run(quiet=True)
        )

        logger.info(f"Adjusted video saved to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to adjust aspect ratio for {video_path}: {e}")
        return video_path  # Return original path if adjustment fails

def post_to_instagram(client, video_path, caption):
    """
    Uploads a video to Instagram with the given caption.
    """
    try:
        # Ensure the video is valid before posting
        if not is_valid_video(video_path):
            logger.error(f"Video {video_path} is invalid or corrupted. Skipping upload.")
            return

        # Upload video
        media = client.video_upload(video_path, caption)
        logger.info(f"Posted video to Instagram with caption: '{caption}'")

        # Wait to respect Instagram's rate limits
        time.sleep(60)  # Wait for 60 seconds
    except Exception as e:
        logger.error(f"Failed to post to Instagram: {e}")

def main():
    if len(sys.argv) != 2:
        logger.error("Usage: python3 main.py <query>")
        sys.exit(1)
    query = sys.argv[1]
    max_videos = 5
    youtube_videos = get_youtube_shorts(query, max_videos)

    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    # Initialize Instagram client
    client = Client()

    try:
        # Attempt to load a saved session
        if os.path.exists("session.json"):
            client.load_settings("session.json")
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        else:
            # Fresh login
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            # Save session for future use
            client.dump_settings("session.json")
        logger.info("Logged in to Instagram successfully.")
    except Exception as e:
        logger.error(f"Login failed: {e}")
        sys.exit(1)

    downloaded_count = 0
    for video_url in youtube_videos:
        if downloaded_count >= max_videos:
            break
        try:
            logger.info(f"\nProcessing YouTube Short: {video_url}")
            output_path = download_youtube_video(video_url)
            if not output_path:
                continue  # Skip if download failed

            # Validate the downloaded video
            if not is_valid_video(output_path):
                logger.error(f"Downloaded video {output_path} is invalid or corrupted. Re-downloading.")
                # Attempt to re-download
                output_path = download_youtube_video(video_url)
                if not output_path or not is_valid_video(output_path):
                    logger.error(f"Failed to obtain a valid video for {video_url}. Skipping.")
                    continue

            # Adjust video aspect ratio using FFmpeg
            adjusted_video_path = adjust_aspect_ratio_ffmpeg(output_path)

            # Post to Instagram
            caption = 'Your caption'  # Replace with your desired caption
            logger.info(f"Posting video to Instagram with caption: '{caption}'")
            post_to_instagram(client, adjusted_video_path, caption)
            downloaded_count += 1
        except Exception as e:
            logger.error(f"Error processing {video_url}: {e}")

    logger.info("\nAll tasks completed.")

if __name__ == "__main__":
    main()
