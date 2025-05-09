# filename: main.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import json

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/search")
def search_youtube(q: str = Query(...)):
    url = f"https://www.youtube.com/results?search_query={q}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    videos_data = []
    for script in soup.find_all("script"):
        if "var ytInitialData" in script.text:
            try:
                json_text = script.string.split(" = ")[1].rsplit(";", 1)[0]
                data = json.loads(json_text)
                videos = data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"]
                for video in videos:
                    if "videoRenderer" in video:
                        title = video["videoRenderer"]["title"]["runs"][0]["text"]
                        video_id = video["videoRenderer"]["videoId"]
                        videos_data.append({"title": title, "videoId": video_id})
                break
            except Exception as e:
                print("Error parsing YouTube data:", e)
    return {"titles": videos_data}
