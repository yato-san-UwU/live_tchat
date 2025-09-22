import uuid, base64
from livetchat.server.ws_manager import ConnectionManager
from livetchat.shared.utils import now_ms
from livetchat.shared.protocol import CHUNK_SIZE

# Mode binaire (ancien) – on le garde si tu veux y revenir un jour
async def broadcast_blob_bin(manager: ConnectionManager, kind: str, *, username: str, display_time: float, display_text: str,
                             content: bytes, content_type: str, start_after_ms: int, exclude: set | None = None,
                             event_id: str | None = None):
    if not event_id:
        event_id = str(uuid.uuid4())
    meta = {
        "type": f"{kind}_start",
        "event_id": event_id,
        "username": username,
        "display_time": float(display_time),
        "display_text": display_text or "",
        "content_type": content_type,
        "content_length": len(content),
        "start_after_ms": int(start_after_ms),
        "server_ts_ms": now_ms(),
        "encoding": "bin",  # <- important pour que le client sache
    }
    await manager.broadcast_json(meta, exclude=exclude)
    total = len(content)
    for i in range(0, total, CHUNK_SIZE):
        await manager.broadcast_bytes(content[i:i+CHUNK_SIZE], exclude=exclude)
    await manager.broadcast_json({"type": f"{kind}_end", "event_id": event_id}, exclude=exclude)
    print(f"[BROADCAST] {kind}/bin {len(content)}B from '{username}' -> {manager.receivers_count(exclude)} client(s)")

# Mode texte/base64 (NOUVEAU) – compatible partout
TEXT_B64_CHUNK = 60_000  # longueur max de la chaîne base64 par chunk (~45 KB bruts)

async def broadcast_blob_textb64(manager: ConnectionManager, kind: str, *, username: str, display_time: float, display_text: str,
                                 content: bytes, content_type: str, start_after_ms: int, exclude: set | None = None,
                                 event_id: str | None = None):
    if not event_id:
        event_id = str(uuid.uuid4())
    b64 = base64.b64encode(content).decode("ascii")
    meta = {
        "type": f"{kind}_start",
        "event_id": event_id,
        "username": username,
        "display_time": float(display_time),
        "display_text": display_text or "",
        "content_type": content_type,
        "content_length": len(content),
        "start_after_ms": int(start_after_ms),
        "server_ts_ms": now_ms(),
        "encoding": "b64",   # <- le client saura qu’il doit lire des chunks texte
    }
    await manager.broadcast_json(meta, exclude=exclude)

    for i in range(0, len(b64), TEXT_B64_CHUNK):
        chunk = b64[i:i+TEXT_B64_CHUNK]
        await manager.broadcast_json({"type": f"{kind}_chunk_b64", "event_id": event_id, "b64": chunk}, exclude=exclude)

    await manager.broadcast_json({"type": f"{kind}_end", "event_id": event_id}, exclude=exclude)
    print(f"[BROADCAST] {kind}/b64 {len(content)}B from '{username}' -> {manager.receivers_count(exclude)} client(s)")
