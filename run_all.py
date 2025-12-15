"""
Utility runner that:
1) copies root credentials into the two project folders
2) runs both automation scripts (Instagram→YouTube, YouTube→Instagram)

Usage examples:
  python run_all.py "cats" ./client_secret.json
  python run_all.py "cats"
If query is omitted, it falls back to SHORTS_QUERY env var.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Paths
ROOT_ENV = ROOT / ".env"
SHORTS_TO_REELS_ENV = ROOT / "reels_shorts" / "shorts_to_reels" / ".env"
REELS_TO_SHORTS_ENV = ROOT / "reels_shorts" / "reels_to_shorts" / ".env"

REELS_TO_SHORTS_GOOGLE_DEST = (
    ROOT / "reels_shorts" / "reels_to_shorts" / "assets" / "token" / "client_secrets.json"
)

SHORTS_TO_REELS_SCRIPT = ROOT / "reels_shorts" / "shorts_to_reels" / "run_shorts_to_reels.py"
REELS_TO_SHORTS_SCRIPT = ROOT / "reels_shorts" / "reels_to_shorts" / "run_reels_to_shorts.py"
REQ_SHORTS_TO_REELS = ROOT / "reels_shorts" / "shorts_to_reels" / "requirements.txt"
REQ_REELS_TO_SHORTS = ROOT / "reels_shorts" / "reels_to_shorts" / "requirements.txt"


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


def copy_file(src: Path, dest: Path, label: str) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Missing {label} at {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"[copied] {label}: {src} -> {dest}")


def run_script(script: Path, args: list[str] | None = None) -> None:
    if not script.exists():
        raise FileNotFoundError(f"Script not found: {script}")
    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)
    print(f"[run] {' '.join(cmd)} (cwd={script.parent})")
    try:
        subprocess.run(cmd, cwd=script.parent, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[error] Script failed: {' '.join(cmd)} (exit {e.returncode})")
        sys.exit(e.returncode)


def install_requirements(requirements_file: Path) -> None:
    if not requirements_file.exists():
        raise FileNotFoundError(f"requirements.txt not found: {requirements_file}")
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
    env = os.environ.copy()
    # Allow PyO3 to build against the stable ABI on newer Python versions (e.g., 3.14)
    env.setdefault("PYO3_USE_ABI3_FORWARD_COMPATIBILITY", "1")
    print(f"[pip] {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"[error] pip install failed for {requirements_file.name} (exit {e.returncode}).")
        sys.exit(e.returncode)


def main() -> None:
    # Python compatibility guard: instagrapi/pydantic pins break on >3.12
    if sys.version_info >= (3, 13):
        sys.exit("Python 3.13+ is not supported by instagrapi/pydantic pins. Please use Python 3.10–3.12.")

    parser = argparse.ArgumentParser(description="Copy creds and run both pipelines.")
    parser.add_argument(
        "query",
        nargs="?",
        help="Search term for YouTube Shorts (used by shorts_to_reels). "
             "Falls back to SHORTS_QUERY env var if omitted.",
    )
    parser.add_argument(
        "google_cred",
        nargs="?",
        help="Path to Google OAuth client secrets JSON for the Instagram→YouTube pipeline. "
             "Defaults to ./client_secret.json or ./client_secrets.json in repo root.",
    )
    args = parser.parse_args()

    query = args.query or os.getenv("SHORTS_QUERY")
    if not query:
        parser.error("You must provide a query (positional) or set SHORTS_QUERY in the environment.")

    # Resolve Google credentials path with sensible defaults
    if args.google_cred:
        google_src = Path(args.google_cred)
        if not google_src.is_absolute():
            google_src = ROOT / google_src
    else:
        # Try common filenames in repo root
        for candidate in ("client_secret.json", "client_secrets.json"):
            maybe = ROOT / candidate
            if maybe.exists():
                google_src = maybe
                break
        else:
            parser.error("Google client secrets not found. Provide a path or place client_secret.json in repo root.")

    # 1) Copy env to both projects
    copy_file(ROOT_ENV, SHORTS_TO_REELS_ENV, ".env (shorts_to_reels)")
    copy_file(ROOT_ENV, REELS_TO_SHORTS_ENV, ".env (reels_to_shorts)")

    # 2) Copy Google client secrets for the Instagram→YouTube flow
    copy_file(google_src, REELS_TO_SHORTS_GOOGLE_DEST, "Google client_secrets.json")

    # 3) Install dependencies for both projects
    install_requirements(REQ_REELS_TO_SHORTS)
    install_requirements(REQ_SHORTS_TO_REELS)
    clear_console()

    # 4) Run pipelines
    run_script(REELS_TO_SHORTS_SCRIPT)  # Instagram Reels -> YouTube Shorts
    clear_console()
    run_script(SHORTS_TO_REELS_SCRIPT, [query])  # YouTube Shorts -> Instagram Reels
    clear_console()


if __name__ == "__main__":
    main()
