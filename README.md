# Repostero

Automation scripts to shuttle short-form videos between Instagram Reels and YouTube Shorts:

- `reels_shorts/reels_to_shorts`: downloads your Instagram reels and uploads them to YouTube Shorts.
- `reels_shorts/shorts_to_reels`: searches YouTube Shorts, downloads them, adjusts aspect ratio, and uploads them as Instagram reels.

## Prerequisites
- Python 3.10+
- FFmpeg installed and on PATH
- A Google account with an active YouTube channel (for uploads)
- Instagram credentials

## Setup
1. Clone and enter the repo:
   ```bash
   git clone http://github.com/germanProgq/repostero
   cd repostero
   ```
2. Create/activate a virtualenv, then install dependencies for both pipelines:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r reels_shorts/reels_to_shorts/requirements.txt
   pip install -r reels_shorts/shorts_to_reels/requirements.txt
   ```
3. Environment:
   - Create `.env` at repo root (or inside each project) with:
     ```
     INSTAGRAM_USERNAME=your_username
     INSTAGRAM_PASSWORD=your_password
     ```
   - For YouTube uploads, place OAuth client secrets at `reels_shorts/reels_to_shorts/assets/token/client_secrets.json` (or adjust paths).

## Workflows
### Instagram Reels ➜ YouTube Shorts
Script: `reels_shorts/reels_to_shorts/run_reels_to_shorts.py`
1. Ensure `client_secrets.json` exists and run once to generate `token.json` when prompted.
2. Run:
   ```bash
   cd reels_shorts/reels_to_shorts
   python run_reels_to_shorts.py
   ```
3. The script:
   - Logs into Instagram (reuses `session.json` if present).
   - Downloads new reels (skips already processed IDs tracked in `processed_reels.json`).
   - Uploads to YouTube Shorts with a simple “Subscribe <emoji>” caption/title.
   - Deletes uploaded files to save space.

### YouTube Shorts ➜ Instagram Reels
Script: `reels_shorts/shorts_to_reels/run_shorts_to_reels.py`
1. Run with a search query:
   ```bash
   cd reels_shorts/shorts_to_reels
   python run_shorts_to_reels.py "cats"
   ```
2. The script:
   - Scrapes YouTube Shorts for the query.
   - Downloads each short (prefers audio+video formats; retries if audio missing).
   - Validates, crops/resizes to 9:16, and uploads to Instagram.
   - Tracks processed YouTube IDs in `processed_shorts.json` and deletes uploaded files.

## Logging and artifacts
- Logs go to `app.log` in each script directory and to stdout with colored levels.
- Temporary downloads live in `reels_shorts/*/downloads`; successful uploads are removed automatically.
- Processed caches: `processed_reels.json`, `processed_shorts.json`.

## Troubleshooting
- Missing FFmpeg: install and ensure `ffmpeg`/`ffprobe` are on PATH.
- YouTube upload limit errors: wait for daily quota reset or switch accounts.
- Instagram login issues: delete `session.json` to force a fresh login, ensure credentials are correct, and avoid frequent logins to reduce risk of challenge prompts.
