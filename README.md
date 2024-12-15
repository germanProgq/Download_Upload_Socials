```markdown
# Shorts_To_Reels

**Shorts_To_Reels** is a Python-based automation tool designed to seamlessly download YouTube Shorts and upload them as Instagram Reels. By leveraging powerful libraries like `instagrapi`, `yt-dlp`, and `ffmpeg-python`, this tool simplifies the process of curating and sharing short-form video content across platforms.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Logging](#logging)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features

- **Search and Retrieve YouTube Shorts:** Fetches YouTube Shorts based on a specified search query.
- **Download Videos:** Downloads selected YouTube Shorts in high-quality MP4 format.
- **Aspect Ratio Adjustment:** Automatically adjusts the video's aspect ratio to 9:16, ideal for Instagram Reels.
- **Upload to Instagram Reels:** Seamlessly uploads processed videos to Instagram with customizable captions.
- **Session Management:** Maintains session persistence to avoid repeated logins and enhance security.
- **Comprehensive Logging:** Logs all operations and errors for easy monitoring and debugging.

## Prerequisites

Before setting up **Shorts_To_Reels**, ensure you have the following installed on your system:

1. **Python:**  
   - Version: **3.10** or higher  
   - Download: [Python Downloads](https://www.python.org/downloads/)

2. **FFmpeg:**  
   - A powerful multimedia framework required for video processing.  
   - **Installation Guide:**  
     - **Windows:**  
       1. Download a static build from [Gyan.dev FFmpeg Builds](https://www.gyan.dev/ffmpeg/builds/).
       2. Extract the ZIP archive to a directory, e.g., `C:\ffmpeg`.
       3. Add `C:\ffmpeg\bin` to your system's PATH.
     - **macOS:**  
       ```bash
       brew install ffmpeg
       ```
     - **Linux (Ubuntu):**  
       ```bash
       sudo apt update
       sudo apt install ffmpeg
       ```
   - **Verify Installation:**  
     ```bash
     ffmpeg -version
     ```

3. **Git (Optional):**  
   - For version control and cloning the repository.  
   - Download: [Git Downloads](https://git-scm.com/downloads)

## Installation

Follow these steps to set up **Shorts_To_Reels** on your local machine:

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Shorts_To_Reels.git
cd Shorts_To_Reels
```

*Replace `yourusername` with your actual GitHub username if applicable.*

### 2. Set Up a Virtual Environment

It's recommended to use a virtual environment to manage project dependencies.

```bash
# Create a virtual environment named 'venv'
python -m venv venv
```

### 3. Activate the Virtual Environment

- **Windows:**

  ```bash
  venv\Scripts\activate
  ```

- **macOS/Linux:**

  ```bash
  source venv/bin/activate
  ```

*Your command prompt should now start with `(venv)` indicating that the virtual environment is active.*

### 4. Install Dependencies

Ensure that `pip` is up-to-date, then install the required packages.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration

### 1. Environment Variables

Create a `.env` file in the project's root directory to securely store your Instagram credentials.

```bash
touch .env
```

**Add the following lines to the `.env` file:**

```dotenv
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password
```

*Replace `your_instagram_username` and `your_instagram_password` with your actual Instagram credentials.*

**Security Tip:**  
Ensure that the `.env` file is included in your `.gitignore` to prevent accidental exposure of sensitive information.

### 2. Customize Script Settings

Within the `main.py` script, you can adjust the following parameters:

- **Search Query:**  
  ```python
  query = 'your_category'  # Replace with your desired search query
  ```

- **Maximum Number of Videos to Process:**  
  ```python
  max_videos = 5  # Adjust as needed
  ```

- **Instagram Caption:**  
  ```python
  caption = 'Your caption'  # Replace with your desired caption
  ```

## Usage

Once everything is set up and configured, you can run the script to automate the process of downloading YouTube Shorts and uploading them to Instagram Reels.

```bash
python main.py
```

### **Workflow Overview:**

1. **Search YouTube Shorts:**  
   The script searches YouTube Shorts based on the specified query and retrieves up to `max_videos` links.

2. **Download Videos:**  
   Downloads each YouTube Short if it hasn't been downloaded previously.

3. **Validate Videos:**  
   Ensures that downloaded videos are not corrupted and have a valid duration.

4. **Adjust Aspect Ratio:**  
   Uses FFmpeg to crop and resize videos to a 9:16 aspect ratio, suitable for Instagram Reels.

5. **Upload to Instagram:**  
   Uploads the processed videos to your Instagram account with the specified caption.

6. **Logging:**  
   All operations, including successes and errors, are logged in the `app.log` file for monitoring and troubleshooting.

## Troubleshooting

Encountering issues? Here's a guide to help you resolve common problems:

### **1. MoviePy Not Detected**

**Issue:**  
`instagrapi` reports that MoviePy is not installed, even after installation.

**Solution:**  
- Ensure that the virtual environment is activated.
- Verify that `moviepy` is installed within the virtual environment:
  ```bash
  pip show moviepy
  ```
- If not installed, reinstall MoviePy:
  ```bash
  pip install moviepy==1.0.3
  ```
- Ensure no local files named `moviepy.py` or directories named `moviepy` exist in your project that could shadow the installed package.

### **2. FFmpeg Not Found**

**Issue:**  
The script fails to process videos, indicating that FFmpeg is not found.

**Solution:**  
- Verify FFmpeg installation by running:
  ```bash
  ffmpeg -version
  ```
- Ensure FFmpeg's `bin` directory is added to your system's PATH.
- Restart your terminal after making changes to PATH.

### **3. Instagram Login Issues**

**Issue:**  
Failed to log in to Instagram, possibly due to Two-Factor Authentication (2FA).

**Solution:**  
- **Handle 2FA:**  
  The script will prompt you to enter the 2FA code if enabled.
- **Verify Credentials:**  
  Double-check your Instagram username and password in the `.env` file.
- **Session Management:**  
  Delete the existing `session.json` file to force a fresh login if encountering persistent login errors.

### **4. Video Upload Failures**

**Issue:**  
Videos fail to upload to Instagram.

**Solution:**  
- **Check Video Compatibility:**  
  Ensure videos meet Instagram's requirements (MP4 format, H.264 codec, AAC audio, 9:16 aspect ratio).
- **Review Logs:**  
  Check `app.log` for detailed error messages.
- **Rate Limiting:**  
  The script includes a delay (`time.sleep(60)`) between uploads to respect Instagram's rate limits. Adjust as necessary.

## Logging

All operations and errors are logged in the `app.log` file located in the project's root directory. This file provides detailed insights into the script's execution flow and is invaluable for troubleshooting.

**Log Entries Include:**

- **Timestamps:** When each operation occurs.
- **Log Levels:** INFO for standard operations, ERROR for issues.
- **Messages:** Descriptions of actions taken and any errors encountered.

*Example Log Entry:*

```
2024-12-15 14:33:53,384 - INFO - Original size: 360x640
2024-12-15 14:33:53,384 - ERROR - Failed to adjust aspect ratio for downloads\OqtsLUIrSVQ.mp4: 'Resize' object has no attribute 'write_videofile'
```

## Contributing

Contributions are welcome! Whether you're fixing bugs, improving documentation, or suggesting new features, your input is valuable.

### **How to Contribute:**

1. **Fork the Repository:**

   Click the "Fork" button at the top right of the repository page to create your own copy.

2. **Clone Your Fork:**

   ```bash
   git clone https://github.com/germanProgq# No code was selected, so I will provide a general improvement to the existing code.

# Improved code for handling Instagram login issues
try:
    # Attempt to log in to Instagram
    instagram.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
except instagrapi.exceptions.LoginRequired:
    # Handle 2FA
    two_fa_code = input("Enter the 2FA code: ")
    instagram.two_factor_login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, two_fa_code)
except instagrapi.exceptions.LoginError:
    # Handle login errors
    print("Failed to log in to Instagram. Please check your credentials.")
    # Delete the existing session.json file to force a fresh login
    if os.path.exists("session.json"):
        os.remove("session.json/Shorts_To_Reels.git
   cd Shorts_To_Reels
   ```

3. **Create a New Branch:**

   ```bash
   git checkout -b feature/YourFeatureName
   ```

4. **Make Changes and Commit:**

   ```bash
   git add .
   git commit -m "Add your descriptive commit message here"
   ```

5. **Push to Your Fork:**

   ```bash
   git push origin feature/YourFeatureName
   ```

6. **Open a Pull Request:**

   Navigate to your fork on GitHub and click "Compare & pull request" to submit your changes for review.

### **Guidelines:**

- **Follow the Coding Standards:** Ensure your code adheres to Python's PEP 8 style guidelines.
- **Write Clear Commit Messages:** Make it easy for reviewers to understand the purpose of your changes.
- **Provide Descriptions for Pull Requests:** Explain what your changes do and why they're necessary.

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

For any questions, issues, or feature requests, feel free to reach out:

- **GitHub Issues:** [Shorts_To_Reels Issues](https://github.com/germanProgq/Shorts_To_Reels/issues)
- **Email:** gvinok@duck.com

---

**Disclaimer:**  
Automating interactions with platforms like Instagram should be done responsibly and in accordance with their [Terms of Service](https://help.instagram.com/581066165581870). Ensure that your usage of this tool complies with all relevant policies to avoid account restrictions or bans.

```