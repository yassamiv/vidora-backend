import json
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import yt_dlp

APP_NAME = "Vidora API"
MAX_ACTIVE = 2
semaphore = threading.BoundedSemaphore(MAX_ACTIVE)

app = FastAPI(title=APP_NAME, version="1.0.0")

# CORS: Hostless ortam değişkeni ve Vidora'nın bilinen frontend adresleri.
allowed_origins = [
    item.strip()
    for item in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if item.strip()
]
allowed_origins.extend([
    "https://vidoraaa.netlify.app",
    "https://silly-torrone-de4d6f.netlify.app",
    "http://localhost:3000",
])
allowed_origins = list(dict.fromkeys(allowed_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"
}
QUALITY_MAP = {"144", "180", "240", "360", "480", "720", "1080", "2160"}

class VideoRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    format: str = "mp4"
    quality: str = "1080"

def validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in ALLOWED_HOSTS:
        raise HTTPException(400, "Yalnızca YouTube veya youtu.be bağlantıları destekleniyor.")
    if parsed.username or parsed.password:
        raise HTTPException(400, "Bu bağlantı biçimi desteklenmiyor.")
    return url.strip()

def ydl_base():
    return {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "extractor_retries": 1,
        "ignoreerrors": False,
    }

@app.get("/")
def home():
    return {"service": APP_NAME, "status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/info")
def info(req: VideoRequest):
    url = validate_url(req.url)
    opts = ydl_base()
    opts["skip_download"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
        return {
            "title": data.get("title") or "Başlıksız video",
            "thumbnail": data.get("thumbnail") or "",
            "duration": data.get("duration"),
            "uploader": data.get("uploader") or "",
        }
    except Exception as exc:
        raise HTTPException(422, "Video bilgisi alınamadı. Bağlantıyı kontrol edip tekrar dene.") from exc

@app.post("/api/download")
def download(req: VideoRequest):
    url = validate_url(req.url)
    fmt = req.format.lower().strip()
    quality = req.quality.lower().strip()
    if fmt not in ("mp4", "mp3"):
        raise HTTPException(400, "Desteklenmeyen biçim.")
    if fmt == "mp4" and quality not in QUALITY_MAP:
        raise HTTPException(400, "Geçersiz video çözünürlüğü.")
    if fmt == "mp3" and quality not in ("standard", "hd"):
        raise HTTPException(400, "Geçersiz MP3 kalitesi.")
    if not semaphore.acquire(blocking=False):
        raise HTTPException(429, "Sunucu şu anda dolu. Biraz sonra tekrar dene.")

    temp_dir = tempfile.mkdtemp(prefix="vidora-")
    try:
        outtmpl = str(Path(temp_dir) / "%(title).120B [%(id)s].%(ext)s")
        opts = ydl_base()
        opts.update({"outtmpl": outtmpl, "restrictfilenames": True, "windowsfilenames": True})
        if fmt == "mp3":
            opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320" if quality == "hd" else "192",
                }],
            })
        else:
            max_height = int(quality)
            opts.update({
                "format": (
                    f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"best[height<={max_height}][ext=mp4]/"
                    f"bestvideo[height<={max_height}]+bestaudio/"
                    f"best[height<={max_height}]"
                ),
                "merge_output_format": "mp4",
            })
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        files = [p for p in Path(temp_dir).iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl"))]
        if not files:
            raise HTTPException(422, "İndirilen dosya oluşturulamadı.")
        # Prefer the final media file if a thumbnail or other sidecar was generated.
        media = [p for p in files if p.suffix.lower() in (".mp4", ".mp3", ".m4a", ".webm", ".mkv")]
        target = max(media or files, key=lambda p: p.stat().st_size)
        safe_name = re.sub(r"[^A-Za-z0-9._ ()\[\]-]", "_", target.name).strip(" .") or ("vidora.mp3" if fmt == "mp3" else "vidora.mp4")
        mime = "audio/mpeg" if target.suffix.lower() == ".mp3" else "video/mp4"
        # FileResponse streams the completed file; the temporary file is removed after response completion.
        async def cleanup():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        response = FileResponse(
            target, media_type=mime, filename=safe_name,
            background=__import__("starlette.background", fromlist=["BackgroundTask"]).BackgroundTask(cleanup)
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except HTTPException:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as exc:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(422, "İndirme başarısız oldu. İçerik erişilebilir olmayabilir veya sunucu sınırına takılmış olabilir.") from exc
    finally:
        semaphore.release()
