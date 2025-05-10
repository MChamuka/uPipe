from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import requests
from bs4 import BeautifulSoup
import json
import subprocess
import yt_dlp
import re
import os

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/search")
def search_youtube(q: str = Query(...)):
    url = f"https://www.youtube.com/results?search_query={q}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    videos = []
    for script in soup.find_all("script"):
        if "var ytInitialData" in script.text:
            try:
                json_text = script.string.split(" = ")[1].rsplit(";", 1)[0]
                data = json.loads(json_text)
                results = data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"]
                for item in results:
                    if "videoRenderer" in item:
                        video = item["videoRenderer"]
                        title = video["title"]["runs"][0]["text"]
                        video_id = video["videoId"]
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        videos.append({
                            "title": title,
                            "videoId": video_id,
                            "url": video_url
                        })
                break
            except Exception as e:
                print("Failed to parse video results:", e)
    return {"videos": videos}


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', '', name)


@app.get("/download_audio")
def download_audio(video_id: str):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"

        # Step 1: Extract video title
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            raw_title = info.get("title", "audio")
            title = sanitize_filename(raw_title)

        # Step 2: Resolve absolute path to cookies.txt
        cookie_file = os.path.abspath("cookies.txt")
        print(f"[DEBUG] Using cookie file at: {cookie_file}")
        print(f"[DEBUG] Current working directory: {os.getcwd()}")

        if not os.path.exists(cookie_file):
            return {"error": f"Cookie file not found: {cookie_file}"}
        if not os.access(cookie_file, os.R_OK):
            return {"error": f"Cookie file not readable: {cookie_file}"}

        # Step 3: Build yt-dlp command
        command = [
            "yt-dlp",
            "--cookies", cookie_file,
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "--extract-audio",
            "--audio-format", "mp3",
            "-o", "-",  # stream to stdout
            url
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def stream_with_error_check():
            for chunk in iter(lambda: process.stdout.read(4096), b""):
                yield chunk
            stderr = process.stderr.read().decode()
            if stderr:
                print("[yt-dlp STDERR]", stderr)

        headers = {
            "Content-Disposition": f'attachment; filename="{title}.mp3"'
        }

        return StreamingResponse(
            stream_with_error_check(),
            media_type="audio/mpeg",
            headers=headers
        )

    except Exception as e:
        print(f"Streaming failed: {e}")
        return {"error": str(e)}


@app.get("/check_cookie_file")
def check_cookie_file():
    cookie_path = os.path.abspath("cookies.txt")
    return {
        "cookie_path": cookie_path,
        "exists": os.path.exists(cookie_path),
        "readable": os.access(cookie_path, os.R_OK),
        "cwd": os.getcwd()
    }
