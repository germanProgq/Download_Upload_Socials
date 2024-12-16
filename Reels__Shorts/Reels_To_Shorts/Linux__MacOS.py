import os
import sys
import time
import logging
import requests
from instagrapi import Client
from dotenv import load_dotenv
from assets.upload_short import upload_all_videos_in_folder, get_authenticated_service
from assets.generate_token__Linux import generate_token

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
CLIENT_SECRETS_FILE = "./assets/token/client_secrets.json"
TOKEN_FILE = "token.json"

def download_instagram_video(client, media_id, download_path=DOWNLOAD_PATH):
    """
    Downloads an Instagram video by its media ID.
    """
    try:
        media_info = client.media_info(media_id)
        video_url = media_info.video_url

        if not video_url:
            logger.warning(f"No video URL found for media ID: {media_id}")
            return None

        # Define the output file path
        output_filename = f"{media_id}.mp4"
        output_path = os.path.join(download_path, output_filename)

        # Download video content
        response = requests.get(video_url, stream=True)
        response.raise_for_status()  # Raise an error for failed HTTP requests
        with open(output_path, 'wb') as video_file:
            for chunk in response.iter_content(chunk_size=1024):
                video_file.write(chunk)

        logger.info(f"Downloaded video to: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Failed to download video for media ID {media_id}: {e}")
        return None


def process_reels(client):
    """
    Processes reels: fetches, downloads, and uploads videos.
    """
    logger.info("Processing reels...")

    try:
        # Fetch recent reels
        reels = client.reels_tray()  # Fetch reels from the user's feed
        if not reels:
            logger.warning("No reels found.")
            return

        logger.info(f"Found {len(reels)} reels.")
        for i, reel in enumerate(reels, start=1):
            logger.info(f"Processing reel {i}/{len(reels)}...")
            download_instagram_video(client, reel.id)
            time.sleep(2)  # Wait to avoid rate limits

    except Exception as e:
        logger.error(f"Error processing reels: {e}")


def main():
    # Ensure a download directory exists
    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    # Initialize Instagram client
    client = Client()

    # Authenticate with Instagram
    try:
        if os.path.exists("session.json"):
            client.load_settings("session.json")
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        else:
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            client.dump_settings("session.json")

        logger.info("Logged in to Instagram successfully.")
    except Exception as e:
        logger.error(f"Login failed: {e}")
        sys.exit(1)

    # Check for YouTube token.json file
    if not os.path.exists(TOKEN_FILE):
        logger.info(f"{TOKEN_FILE} not found. Generating a new token...")
        try:
            generate_token(CLIENT_SECRETS_FILE, TOKEN_FILE)
            logger.info(f"Token generated and saved to {TOKEN_FILE}.")
        except Exception as e:
            logger.error(f"Failed to generate token: {e}")
            sys.exit(1)

    # Process reels
    process_reels(client)

    # Authenticate with YouTube and upload videos
    try:
        youtube = get_authenticated_service()
        upload_all_videos_in_folder(youtube, DOWNLOAD_PATH)
    except Exception as e:
        logger.error(f"Error uploading videos to YouTube: {e}")

    logger.info("All tasks completed.")


if __name__ == "__main__":
    main()
