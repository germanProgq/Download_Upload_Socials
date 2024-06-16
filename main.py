import os
import requests
from moviepy.editor import VideoFileClip
from instagram_private_api import Client, ClientCompatPatch
import yt_dlp as youtube_dl
import tempfile
from PIL import Image

# Define constants
DOWNLOAD_PATH = os.path.join('your_download_folder', 'videos')
INSTAGRAM_USERNAME = 'your_ig_user'
INSTAGRAM_PASSWORD = 'your_ig_pass'

def get_youtube_shorts(query, max_results=5):
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
            video_ids.add(video_id)
            page_content = page_content[index+19:]

        for video_id in video_ids:
            video_urls.append(f"https://www.youtube.com/shorts/{video_id}")
    return video_urls

def download_youtube_video(video_url):
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
        output_path = temp_video.name
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    return output_path


def adjust_aspect_ratio(video_path, target_width=1080, target_height=1920):
    print(f"Adjusting aspect ratio for {video_path}")
    clip = VideoFileClip(video_path)
    width, height = clip.size
    print(f"Original size: {width}x{height}")
    target_aspect_ratio = target_width / target_height

    # Crop video to the target aspect ratio
    if width / height > target_aspect_ratio:
        new_width = int(height * target_aspect_ratio)
        x1 = (width - new_width) // 2
        x2 = x1 + new_width
        clip = clip.crop(x1=x1, x2=x2)
    elif width / height < target_aspect_ratio:
        new_height = int(width / target_aspect_ratio)
        y1 = (height - new_height) // 2
        y2 = y1 + new_height
        clip = clip.crop(y1=y1, y2=y2)

    # Resize to the target resolution
    clip_resized = clip.resize(newsize=(target_width, target_height))
    output_path = tempfile.mktemp(suffix='.mp4')
    clip_resized.write_videofile(output_path, codec='libx264', audio_codec='aac')
    print(f"Adjusted video saved to {output_path}")

    return output_path

def post_to_instagram(api, video_path, caption):
    try:
        clip = VideoFileClip(video_path)
        duration = int(clip.duration)
        width, height = clip.size
        aspect_ratio = width / height

        if not (0.5625 <= aspect_ratio <= 1.91):
            print(f"Adjusting aspect ratio for {video_path}")
            video_path = adjust_aspect_ratio(video_path)
            clip = VideoFileClip(video_path)
            width, height = clip.size
            aspect_ratio = width / height
            print(f"Adjusted video size: {width}x{height}, aspect ratio: {aspect_ratio}")

        thumbnail_path = tempfile.mktemp(suffix='.jpg')
        clip.save_frame(thumbnail_path, t=(duration / 2))

        with open(video_path, 'rb') as video_file, open(thumbnail_path, 'rb') as thumb_file:
            video_data = video_file.read()
            thumbnail_data = thumb_file.read()

        api.post_video(video_data, size=(width, height), duration=duration, thumbnail_data=thumbnail_data, caption=caption, to_reel=True)
    except Exception as e:
        print(f"Failed to post to Instagram: {e}")

def main():
    query = 'your_category'
    max_videos = 5
    youtube_videos = get_youtube_shorts(query, max_videos)

    if not os.path.exists(DOWNLOAD_PATH):
        os.makedirs(DOWNLOAD_PATH)

    api = Client(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

    downloaded_count = 0
    for video_url in youtube_videos:
        if downloaded_count >= max_videos:
            break
        try:
            output_path = download_youtube_video(video_url)
            caption = 'Your caption'
            post_to_instagram(api, output_path, caption)
            downloaded_count += 1
        except Exception as e:
            print(f"Error processing {video_url}: {e}")

if __name__ == '__main__':
    main()

