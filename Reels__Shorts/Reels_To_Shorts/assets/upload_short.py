import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

def get_authenticated_service(token_file="token.json"):
    """
    Authenticate with the YouTube Data API using the `token.json` file.

    Args:
        token_file (str): Path to the token JSON file.

    Returns:
        googleapiclient.discovery.Resource: Authenticated YouTube API client.
    """
    credentials = Credentials.from_authorized_user_file(
        token_file, scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    return build("youtube", "v3", credentials=credentials)

def upload_video(youtube, video_file, title, description, category_id=22, privacy_status="public"):
    """
    Upload a video to YouTube.

    Args:
        youtube: Authenticated YouTube API client.
        video_file (str): Path to the video file.
        title (str): Title of the video.
        description (str): Description of the video.
        category_id (int): Category ID for the video (default is 22 for "People & Blogs").
        privacy_status (str): Privacy status ("public", "private", or "unlisted").
    """
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": str(category_id),
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()

    print(f"Video uploaded successfully: https://www.youtube.com/watch?v={response['id']}")
    return response

def upload_all_videos_in_folder(youtube, folder_path, category_id=22, privacy_status="public"):
    """
    Upload all videos in the specified folder to YouTube.

    Args:
        youtube: Authenticated YouTube API client.
        folder_path (str): Path to the folder containing video files.
        category_id (int): Category ID for the videos.
        privacy_status (str): Privacy status for the videos.
    """
    # Get a list of all video files in the folder
    video_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]

    if not video_files:
        print("No video files found in the specified folder.")
        return

    for video_file in video_files:
        video_path = os.path.join(folder_path, video_file)

        # Generate a title and description based on the file name
        title = "Something"
        description = f"Subscribe and Like!"

        print(f"Uploading: {video_file}")
        try:
            upload_video(youtube, video_path, title, description, category_id, privacy_status)
        except Exception as e:
            print(f"Failed to upload {video_file}: {e}")
