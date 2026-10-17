import io, os, re, shutil, tempfile, zipfile, ipaddress, socket
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, HttpUrl
import yt_dlp

APP_ORIGINS = [x.strip() for x in os.getenv("DECIBEL_ALLOWED_ORIGINS", "https://thereisfarq.github.io").split(",") if x.strip()]
MAX_UPLOAD = int(os.getenv("DECIBEL_MAX_UPLOAD_MB", "250")) * 1024 * 1024
MAX_DURATION = int(os.getenv("DECIBEL_MAX_DURATION_SECONDS", "7200"))
ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com", "vimeo.com", "www.vimeo.com", "tiktok.com", "www.tiktok.com", "instagram.com", "www.instagram.com", "soundcloud.com", "www.soundcloud.com", "dailymotion.com", "www.dailymotion.com"}

app = FastAPI(title="Decibel API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=APP_ORIGINS, allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])

class ConvertRequest(BaseModel):
    url: HttpUrl
    format: str = "mp3"
    quality: str = "192"

def validate_url(raw: str):
    u = urlparse(raw)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise HTTPException(400, "Only public http/https media URLs are supported.")
    host = u.hostname.lower()
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise HTTPException(400, "Private or local network addresses are not allowed.")
    except ValueError:
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            raise HTTPException(400, "Private or local network addresses are not allowed.")
        try:
            resolved = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}
            if any(not ip.is_global for ip in resolved):
                raise HTTPException(400, "Private or local network addresses are not allowed.")
        except socket.gaierror:
            pass
    if not (host in ALLOWED_HOSTS or host.endswith(".youtube.com") or host.endswith(".vimeo.com")):
        ext = Path(u.path).suffix.lower()
        if ext not in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".webm", ".mov", ".mkv", ".m4v"}:
            raise HTTPException(400, "This host is not on the supported platform list. Use a direct media file URL or a supported platform.")
    return raw

def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return (value[:90] or "decibel_export")

@app.get("/health")
def health():
    return {"ok": True, "service": "decibel-api", "max_upload_mb": MAX_UPLOAD // (1024*1024), "max_duration_seconds": MAX_DURATION}

@app.post("/api/info")
def info(req: ConvertRequest):
    url = validate_url(str(req.url))
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True, "socket_timeout": 15}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
        duration = int(data.get("duration") or 0)
        if duration > MAX_DURATION:
            raise HTTPException(413, f"Media is longer than the {MAX_DURATION // 60}-minute service limit.")
        return {"title": data.get("title") or "Media link", "duration": duration, "thumbnail": data.get("thumbnail"), "extractor": data.get("extractor_key"), "formats": ["mp3", "mp4", "wav", "webm"]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, f"Could not read this media link: {str(exc)[:300]}")

@app.post("/api/convert")
def convert(req: ConvertRequest):
    url = validate_url(str(req.url))
    fmt = req.format.lower()
    if fmt not in {"mp3", "mp4", "wav", "webm"}:
        raise HTTPException(400, "Choose MP3, MP4, WAV or WebM.")
    quality = req.quality if req.quality in {"128", "192", "256", "320"} else "192"
    with tempfile.TemporaryDirectory(prefix="decibel-") as tmp:
        opts = {"outtmpl": str(Path(tmp) / "%(title).80s.%(ext)s"), "noplaylist": True, "quiet": True, "no_warnings": True, "socket_timeout": 20, "max_filesize": MAX_UPLOAD, "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {MAX_DURATION}")}
        if fmt in {"mp3", "wav"}:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": fmt, "preferredquality": quality if fmt == "mp3" else "0"}]
        else:
            opts["format"] = "bestvideo*+bestaudio/best"
            opts["merge_output_format"] = fmt
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info_data = ydl.extract_info(url, download=True)
            candidates = [p for p in Path(tmp).iterdir() if p.is_file() and p.suffix.lower() in {".mp3", ".mp4", ".wav", ".webm", ".m4a", ".mkv"}]
            if not candidates:
                raise RuntimeError("The converter produced no output file.")
            output = max(candidates, key=lambda p: p.stat().st_size)
            if output.stat().st_size > MAX_UPLOAD:
                raise HTTPException(413, "The converted file exceeds the service size limit.")
            persistent = tempfile.NamedTemporaryFile(delete=False, suffix=output.suffix, prefix="decibel-out-")
            persistent.close()
            shutil.copyfile(output, persistent.name)
            return FileResponse(persistent.name, filename=safe_name(info_data.get("title") or "decibel") + "." + fmt, media_type={"mp3":"audio/mpeg","wav":"audio/wav","mp4":"video/mp4","webm":"video/webm"}[fmt], background=BackgroundTask(os.unlink, persistent.name))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, f"Conversion failed: {str(exc)[:350]}")

@app.post("/api/separate")
async def separate(file: UploadFile = File(...)):
    name = safe_name(file.filename or "audio")
    ext = Path(name).suffix.lower()
    if ext not in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".webm", ".mov", ".mkv"}:
        raise HTTPException(400, "Unsupported audio/video file type.")
    with tempfile.TemporaryDirectory(prefix="decibel-stems-") as tmp:
        input_path = Path(tmp) / name
        size = 0
        with input_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, f"Upload exceeds {MAX_UPLOAD // (1024*1024)} MB.")
                out.write(chunk)
        try:
            from audio_separator.separator import Separator
            outdir = Path(tmp) / "stems"
            outdir.mkdir()
            separator = Separator(output_dir=str(outdir), output_format="WAV", normalization_threshold=0.9)
            separator.load_model(model_filename="UVR-MDX-NET-Inst_HQ_3.onnx")
            output_names = separator.separate(str(input_path))
            files = [outdir / n for n in output_names if (outdir / n).is_file()]
            if len(files) < 2:
                files = list(outdir.glob("*.wav"))
            if not files:
                raise RuntimeError("The AI model returned no stem files.")
            archive = Path(tmp) / "decibel-stems.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in files:
                    zf.write(p, p.name)
            data = archive.read_bytes()
            return StreamingResponse(io.BytesIO(data), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="decibel-stems.zip"'})
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(500, f"AI separation failed. Confirm the model downloaded successfully and the server has enough RAM. Details: {str(exc)[:250]}")
