# Instagram-to-Shorts Tool

Automates downloading Instagram Reels and uploading them as YouTube Shorts using `instagrapi` and the YouTube Data API.

---

## Quick start
1. Clone and enter the project:
   ```bash
   git clone https://github.com/germanProgq/Download_Upload_Socials.git
   cd Download_Upload_Socials/reels_shorts/reels_to_shorts
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Add Instagram credentials in a `.env` file:
   ```
   INSTAGRAM_USERNAME=your_username
   INSTAGRAM_PASSWORD=your_password
   ```
4. Enable the YouTube Data API in your Google Cloud project and download `client_secret.json` (OAuth client for Desktop). Place it at `assets/token/client_secrets.json`.
5. Generate a YouTube `token.json` (pick one):
   - Desktop flow (opens browser): `python assets/youtube_token_desktop.py`
   - Headless/SSH flow: `python assets/youtube_token_headless.py`
6. Run the pipeline (auto-detects Windows vs. macOS/Linux): `python run_reels_to_shorts.py`

Downloaded reels land in `downloads` and are then uploaded to YouTube.

---

## What the scripts do
- `run_reels_to_shorts.py`: Logs into Instagram, downloads recent reels, and uploads everything in `downloads/` to YouTube. If `token.json` is missing it chooses the desktop (Windows) or headless (macOS/Linux/SSH) OAuth flow automatically.
- `assets/youtube_token_desktop.py`: Launches the browser OAuth flow and writes `token.json`.
- `assets/youtube_token_headless.py`: Prints a copy/paste OAuth URL for terminals without a browser and writes `token.json`.
- `assets/youtube_upload.py`: Shared helpers for creating the YouTube client and uploading every video in a folder.

---

## How credentials are handled
- **Instagram**: Username/password are read from `.env` via `python-dotenv`. After the first login, a `session.json` file is saved locally and reused so you are not prompted again unless Instagram requires a fresh login.
- **YouTube**: OAuth uses your Google Cloud OAuth client (`assets/token/client_secrets.json`). On first run you approve the scopes, then `token.json` is stored locally and reused for uploads. No secrets are sent anywhere except directly to Google's OAuth endpoint during the normal login flow.

---

## Notes
1. Ensure your videos meet YouTube's [upload requirements](https://support.google.com/youtube/answer/57407).
2. The upload helpers currently assign a placeholder title/description—adjust in `assets/youtube_upload.py` before bulk uploads.
3. Avoid mass uploads in a short window to stay within API quotas.
4. Reel downloads are multithreaded (up to 8 workers by default); tune `MAX_DOWNLOAD_WORKERS` near the top of `run_reels_to_shorts.py` if you need to throttle or speed up downloads on your machine.
