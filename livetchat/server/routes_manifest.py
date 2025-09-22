from fastapi import APIRouter
from fastapi.responses import JSONResponse
from livetchat.server import settings
from livetchat.shared.version import VERSION
import hashlib, os

router = APIRouter()

EXE_NAME = "TchatLive.exe"
EXE_PATH = os.path.join(settings.DOWNLOAD_DIR, EXE_NAME)
EXE_URL  = f"{settings.PUBLIC_BASE_URL}/downloads/{EXE_NAME}"

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

@router.get("/manifest.json")
async def manifest():
    return JSONResponse({
        "version": VERSION,
        "url": EXE_URL,
        "sha256": sha256_file(EXE_PATH),   # recalcul à chaque requête (évite l’oubli)
        "notes": "Live-only; images/videos/audio; overlays."
    })
