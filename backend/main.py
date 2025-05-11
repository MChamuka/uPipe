from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import requests
from bs4 import BeautifulSoup
import json
import re
import os
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

        # Setup yt-dlp options
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'extractaudio': True,
            'audioformat': 'mp3',
            'cookiefile': cookie_file,
            'quiet': True,
            'noplaylist': True,
            'outtmpl': '-',
            'logtostderr': True,
            'verbose': True
        }

        # Create a streaming generator using yt-dlp
        def generate():
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(url, download=False)
                    title = sanitize_filename(result.get("title", "audio"))

                    # Run download and stream
                    ydl.params["outtmpl"] = "-"
                    ydl.download([url])

            except DownloadError as de:
                yield f"[DownloadError] {de}".encode()
            except Exception as e:
                yield f"[Error] {e}".encode()

        # Try to extract title for filename
        try:
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = sanitize_filename(info.get("title", "audio"))
        except:
            title = "audio"

        headers = {
            "Content-Disposition": f'attachment; filename="{title}.mp3"'
        }

        return StreamingResponse(
            generate(),
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
