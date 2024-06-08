# YouTube Shorts to Instagram Reels

This project downloads YouTube Shorts videos, adjusts their aspect ratios if necessary, and posts them to Instagram Reels.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.6 or higher
- The following Python libraries:
  - `requests`
  - `moviepy`
  - `instagram_private_api`
  - `yt_dlp`
  - `Pillow`
- An Instagram account

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/germanProgq/shorts-to-reels.git
   cd shorts-to-reels
   ```

2. Install the required libraries:

   ```bash
   pip install requests moviepy instagram_private_api yt-dlp Pillow
   ```

## Usage

1. Update the constants in the script with your Instagram credentials:

   ```python
   INSTAGRAM_USERNAME = 'your_instagram_username'
   INSTAGRAM_PASSWORD = 'your_instagram_password'
   ```

2. Run the script:

   ```bash
   python script.py
   ```

   The script will:
   - Search YouTube for Shorts videos based on a query.
   - Download the videos.
   - Adjust the aspect ratios if necessary.
   - Post the videos to Instagram Reels.

## Functions

### `get_youtube_shorts(query, max_results=5)`

Searches for YouTube Shorts videos based on the query and returns a list of video URLs.

- `query`: The search query.
- `max_results`: The maximum number of video URLs to return.

### `download_youtube_video(video_url, output_path)`

Downloads a YouTube video from the provided URL to the specified output path.

- `video_url`: The URL of the YouTube video.
- `output_path`: The path to save the downloaded video.

### `adjust_aspect_ratio(video_path, target_width=1080, target_aspect_ratio=0.5625)`

Adjusts the aspect ratio of a video to fit the target aspect ratio.

- `video_path`: The path of the video to adjust.
- `target_width`: The target width of the video.
- `target_aspect_ratio`: The target aspect ratio (default is 0.5625 for 9:16 aspect ratio).

### `post_to_instagram(api, video_path, caption)`

Posts a video to Instagram Reels.

- `api`: The Instagram API client.
- `video_path`: The path of the video to post.
- `caption`: The caption for the Instagram post.

## Notes

- Ensure your Instagram account is in good standing and can post videos.
- The YouTube Shorts URL parsing might break if YouTube changes its HTML structure. Consider using the YouTube Data API for a more robust solution.

## Contributing

Contributions are welcome! Please fork the repository and create a pull request with your changes.

## License

This project is open-source and available under the [MIT License](LICENSE).

---

Replace placeholders like `your_ig_username`, `your_ig_password`, and the repository URL with your actual information.