# Instagram-to-Shorts Tool

This project provides a Python script to automate the process of downloading Instagram Reels and uploading them as YouTube Shorts. It uses the Instagram API (via `instagrapi`) to fetch Reels and the YouTube Data API to upload videos.

---

## Features

- **Download Instagram Reels**: Automatically downloads Reels from a specified Instagram account or feed.
- **Batch Upload to YouTube Shorts**: Uploads all downloaded videos to YouTube as Shorts.
- **Dynamic Titles and Descriptions**: Generates video titles based on file names and assigns default descriptions.
- **Customizable Privacy Settings**: Supports public, private, and unlisted privacy settings for uploaded videos.
- **Error Handling**: Logs errors for any failed downloads or uploads and continues with the next video.

---

## Requirements

- Python 3.7+
- A Google Cloud project with the YouTube Data API enabled.
- Instagram account credentials (for downloading Reels).
- A valid `token.json` file for YouTube API authentication.

---

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/germanProgq/Download_Upload_Socials.git
   cd instagram-to-shorts
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Google Cloud Project**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a project and enable the YouTube Data API.
   - Create credentials and download the `client_secret.json` file.
   - Generate a `token.json` file by running the authentication process (see below).

4. **Configure Instagram Authentication**:
   - Install `instagrapi` for accessing Instagram Reels.
   - Use your Instagram account credentials to log in via the script.

5. **Place Required Files**:
   - Save `client_secret.json` and `token.json` in the project directory.

---

## Usage

### Step 1: Authenticate with YouTube API

Run the script to authenticate with the YouTube API:
```bash
python script_name.py
```
This will prompt you to log in to your Google account and authorize access. A `token.json` file will be created for future use.

### Step 2: Log in to Instagram

The script will prompt you to log in to Instagram using your account credentials. If successful, the session will be saved for reuse.

### Step 3: Download and Upload Videos

1. The script will download Instagram Reels into the `downloads` folder (or a folder you specify).
2. It will then upload the downloaded videos as YouTube Shorts.

Run the script:
```bash
python script_name.py
```

---

## Configuration

You can customize the following in the script:

- **Instagram Source**: Specify whether to download Reels from your feed, another user's profile, or specific hashtags.
- **Folder Path**: Change the `folder_path` variable to point to the folder where videos will be downloaded and processed.
- **Category ID**: Modify the `category_id` in the `upload_video` function to specify a different YouTube video category.
- **Privacy Settings**: Set the `privacy_status` parameter to `"public"`, `"private"`, or `"unlisted"`.

---

## Example

### Folder Structure:
```
project-directory/
├── downloads/
│   ├── reel1.mp4
│   ├── reel2.mov
│   └── reel3.avi
├── client_secret.json
├── token.json
├── script_name.py
├── requirements.txt
└── README.md
```

### Sample Output:
```
Downloading: reel1.mp4
Downloaded successfully to: downloads/reel1.mp4
Uploading: reel1.mp4
Video uploaded successfully: https://www.youtube.com/watch?v=abcd1234
Downloading: reel2.mov
Downloaded successfully to: downloads/reel2.mov
Uploading: reel2.mov
Video uploaded successfully: https://www.youtube.com/watch?v=efgh5678
```

---

## Dependencies

- `google-api-python-client`: For interacting with the YouTube Data API.
- `google-auth`: For handling authentication with Google APIs.
- `instagrapi`: For accessing Instagram Reels.

Install all dependencies using:
```bash
pip install -r requirements.txt
```

---

## Notes

1. Ensure your videos conform to YouTube's [upload requirements](https://support.google.com/youtube/answer/57407).
2. Avoid uploading too many videos in a short period to prevent API quota exhaustion.
3. Use meaningful file names for videos as they are used for generating titles.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
