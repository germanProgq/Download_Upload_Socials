import os
import sys
import time
import logging
import requests
from instagrapi import Client

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

# Constants
DOWNLOAD_PATH = os.path.join('videos')  # Path to save downloaded videos
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

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
        with open(output_path, 'wb') as video_file:
            for chunk in response.iter_content(chunk_size=1024):
                video_file.write(chunk)

        logger.info(f"Downloaded video to: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Failed to download video for media ID {media_id}: {e}")
        return None

def main():
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

    # Retrieve user ID for your account
    try:
        logger.info(f"Fetching feed")

        # Fetch user's feed
        feed = client.reels(amount=20)
        video_posts = [post for post in feed if post.media_type == 2]  # Media type 2 indicates videos

        logger.info(f"Found {len(video_posts)} video posts in your feed.")
        for i, post in enumerate(video_posts[:10], start=1):  # Limit to 10 videos
            logger.info(f"Processing video {i}/{min(10, len(video_posts))}...")
            download_instagram_video(client, post.pk)
            time.sleep(2)  # Wait to avoid triggering rate limits
        # Assuming get_authenticated_service and upload_all_videos_in_folder are correctly implemented elsewhere
        # youtube = get_authenticated_service()
        # upload_all_videos_in_folder(youtube, DOWNLOAD_PATH)
    except Exception as e:
        logger.error(f"Error fetching or downloading feed videos: {e}")
    

    logger.info("All tasks completed.")

if __name__ == "__main__":
    main()