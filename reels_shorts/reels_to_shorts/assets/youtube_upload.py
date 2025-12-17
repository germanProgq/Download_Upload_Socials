import os
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Scopes for upload; must match the token generation scripts.
UPLOAD_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class UploadLimitExceeded(RuntimeError):
    """Raised when the YouTube API reports the daily upload limit is reached."""
    pass


def _extract_error_reason(error: HttpError):
    """
    Pull a stable reason code from a Google API HttpError.
    """
    try:
        for detail in error.error_details or []:
            reason = detail.get("reason")
            if reason:
                return reason
    except Exception:
        pass

    try:
        payload = json.loads(error.content.decode("utf-8"))
        errors = payload.get("error", {}).get("errors", [])
        if errors:
            return errors[0].get("reason")
    except Exception:
        pass

    text = str(error)
    for key in ("uploadLimitExceeded", "insufficientPermissions", "youtubeSignupRequired"):
        if key in text:
            return key
    return None


def _short_error_text(error: Exception) -> str:
    text = str(error).strip()
    if not text:
        return error.__class__.__name__
    return text.split("\n", 1)[0]


def get_authenticated_service(token_file="token.json"):
    """
    Authenticate with the YouTube Data API using the `token.json` file.

    Args:
        token_file (str): Path to the token JSON file.

    Returns:
        googleapiclient.discovery.Resource: Authenticated YouTube API client.
    """
    credentials = Credentials.from_authorized_user_file(token_file, scopes=UPLOAD_SCOPES)
    if not credentials or not credentials.scopes or UPLOAD_SCOPES[0] not in credentials.scopes:
        raise RuntimeError(
            "token.json is missing the youtube.upload scope. Delete token.json, "
            "rerun the token generator script, and approve the YouTube upload scope."
        )

    youtube = build("youtube", "v3", credentials=credentials)

    return youtube

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
    try:
        response = request.execute()
    except HttpError as e:
        reason = _extract_error_reason(e)
        if reason == "uploadLimitExceeded":
            raise UploadLimitExceeded("YouTube upload limit exceeded for this account.") from e
        message = str(e)
        if e.resp.status == 401 and "youtubeSignupRequired" in message:
            raise RuntimeError(
                "Upload unauthorized: the authorized Google account must have an active YouTube channel. "
                "Create/enable a channel for this account, regenerate token.json with the upload scope, and retry."
            ) from e
        if e.resp.status == 403 and "insufficientPermissions" in message:
            raise RuntimeError(
                "Upload failed: token.json does not have the youtube.upload scope. "
                "Delete token.json, regenerate it via the token script (ensure YouTube upload scope is selected), and rerun."
            ) from e
        raise

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

        # Generate a title and description based on the file name with simple tags
        base_title = os.path.splitext(video_file)[0].replace('_', ' ').strip() or "Short"
        tags = "#shorts #reels #viral #subscribe"
        title = f"{base_title} | Shorts"
        description = f"{base_title}\n\n{tags}"

        print(f"Uploading: {video_file}")
        try:
            upload_video(youtube, video_path, title, description, category_id, privacy_status)
        except UploadLimitExceeded:
            print("YouTube upload limit exceeded; stopping remaining uploads to avoid repeated errors.")
            break
        except HttpError as e:
            reason = _extract_error_reason(e)
            print(f"Failed to upload {video_file}: {_short_error_text(e)}")
            if reason == "uploadLimitExceeded":
                print("YouTube upload limit exceeded; stopping remaining uploads to avoid repeated errors.")
                break
        except Exception as e:
            print(f"Failed to upload {video_file}: {_short_error_text(e)}")
