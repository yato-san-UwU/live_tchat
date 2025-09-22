# livetchat/server/main.py
import os
import hashlib
import json
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    UploadFile, File, Form, Request
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from livetchat.server.ws_manager import ConnectionManager
from livetchat.server import settings
from livetchat.server.routes_manifest import router as manifest_router  # /manifest.json

# ------------------------------------------------------------
# App & CORS
# ------------------------------------------------------------
app = FastAPI(title="LiveTchat — HTTP upload + WS notif")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Exposer le dossier de téléchargement des mises à jour (pour l'exe)
try:
    app.mount("/downloads", StaticFiles(directory=settings.DOWNLOAD_DIR), name="downloads")
except Exception as e:
    print("[WARN] downloads mount skipped:", e)

# Route manifest (version, url, sha256)
app.include_router(manifest_router)

# ------------------------------------------------------------
# Dossiers de stockage médias (tu peux aussi les définir dans settings.py)
# ------------------------------------------------------------
IMAGE_DIR = getattr(settings, "IMAGE_DIR", "/home/user/final_livetchat/images")
VIDEO_DIR = getattr(settings, "VIDEO_DIR", "/home/user/final_livetchat/videos")
AUDIO_DIR = getattr(settings, "AUDIO_DIR", "/home/user/final_livetchat/audios")
for d in (IMAGE_DIR, VIDEO_DIR, AUDIO_DIR):
    os.makedirs(d, exist_ok=True)

# ------------------------------------------------------------
# WS manager & utilitaires
# ------------------------------------------------------------
manager = ConnectionManager()
stored_hashes: set[str] = set()   # dédup simple en mémoire (hash contenu)

def md5(data: bytes) -> str:
    h = hashlib.md5()
    h.update(data)
    return h.hexdigest()

def classify(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif"):
        return "image"
    if ext in (".mp4",):
        return "video"
    if ext in (".mp3", ".wav", ".ogg", ".m4a"):
        return "audio"
    return "unknown"

def folder_for(kind: str) -> str:
    return IMAGE_DIR if kind == "image" else VIDEO_DIR if kind == "video" else AUDIO_DIR

# ------------------------------------------------------------
# HTTP: Upload
# ------------------------------------------------------------
@app.post("/upload/")
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    display_time: float = Form(...),
    display_text: str = Form(""),
    username: str = Form("guest"),
):
    data = await file.read()
    size = len(data)
    ip = request.client.host if request.client else "?"
    kind = classify(file.filename)

    if kind == "unknown":
        print(f"[UPLOAD] REJECT {ip} user='{username}' name='{file.filename}' reason=unsupported")
        return JSONResponse({"error": "UNSUPPORTED_FORMAT"}, status_code=400)

    # enregistrer (avec déduplication simple par MD5)
    h = md5(data)
    folder = folder_for(kind)
    filename = f"{h}_{file.filename}"
    path = os.path.join(folder, filename)
    is_new = False

    if h not in stored_hashes or not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(data)
        stored_hashes.add(h)
        is_new = True

    print(
        f"[UPLOAD] {ip} user='{username}' kind={kind} name='{file.filename}' "
        f"saved='{filename}' size={size}B md5={h} new={is_new}"
    )

    # notifier tous les clients via WS
    notice = {
        "type": "media_notice",
        "kind": kind,
        "filename": filename,
        "display_time": float(display_time),
        "display_text": display_text or "",
        "username": username or "guest",
        "is_new": is_new,
    }
    await manager.broadcast_json(notice)
    print(f"[NOTICE] {kind} '{filename}' -> {manager.receivers_count()} client(s)")

    return {"filename": filename, "kind": kind, "is_new": is_new}

# ------------------------------------------------------------
# HTTP: Récupération des fichiers (avec logs)
# ------------------------------------------------------------
@app.get("/files/images/{filename}")
def get_image(filename: str, request: Request):
    path = os.path.join(IMAGE_DIR, filename)
    ip = request.client.host if request.client else "?"
    if not os.path.isfile(path):
        print(f"[GET-404] image {filename} from {ip}")
        return JSONResponse({"error": "not_found"}, status_code=404)
    print(f"[GET] image {filename} to {ip}")
    return FileResponse(path)

@app.get("/files/videos/{filename}")
def get_video(filename: str, request: Request):
    path = os.path.join(VIDEO_DIR, filename)
    ip = request.client.host if request.client else "?"
    if not os.path.isfile(path):
        print(f"[GET-404] video {filename} from {ip}")
        return JSONResponse({"error": "not_found"}, status_code=404)
    print(f"[GET] video {filename} to {ip}")
    return StreamingResponse(open(path, "rb"), media_type="video/mp4")

@app.get("/files/audios/{filename}")
def get_audio(filename: str, request: Request):
    path = os.path.join(AUDIO_DIR, filename)
    ip = request.client.host if request.client else "?"
    if not os.path.isfile(path):
        print(f"[GET-404] audio {filename} from {ip}")
        return JSONResponse({"error": "not_found"}, status_code=404)
    print(f"[GET] audio {filename} to {ip}")
    return StreamingResponse(open(path, "rb"), media_type="application/octet-stream")

# (Optionnel) petites listes pour debug
@app.get("/files/images/")
def list_images(): return os.listdir(IMAGE_DIR)
@app.get("/files/videos/")
def list_videos(): return os.listdir(VIDEO_DIR)
@app.get("/files/audios/")
def list_audios(): return os.listdir(AUDIO_DIR)

# ------------------------------------------------------------
# WebSocket: /ws (keep-open; notifications envoyées depuis /upload/)
# ------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        # on ne s'échange pas de messages applicatifs ; on bloque sur lecture
        while True:
            # ping/pong bas niveau garde la connexion; ici on attend juste un texte
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)

# ------------------------------------------------------------
# Entrée
# ------------------------------------------------------------
def main():
    import uvicorn
    uvicorn.run(
        "livetchat.server.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        access_log=False,
    )

if __name__ == "__main__":
    main()
