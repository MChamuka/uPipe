from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import requests
from bs4 import BeautifulSoup
import json
import subprocess
import yt_dlp
import re
import os
from tempfile import NamedTemporaryFile

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
        cookie_file = os.path.abspath("cookies.txt")

        if not os.path.exists(cookie_file):
            return {"error": f"Cookie file not found at {cookie_file}"}
        if not os.access(cookie_file, os.R_OK):
            return {"error": f"Cookie file not readable: {cookie_file}"}

        # Get video title
        with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': cookie_file}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = sanitize_filename(info.get("title", "audio"))

        # Create a temp file to store MP3
        with NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_path = temp_file.name

        # Download audio as mp3 to temp path
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'cookiefile': cookie_file,
            'quiet': True,
            'noplaylist': True,
            'outtmpl': temp_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Serve the MP3 file to client
        return FileResponse(
            path=temp_path,
            media_type="audio/mpeg",
            filename=f"{title}.mp3",
        )

    except Exception as e:
        print(f"Download failed: {e}")
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
