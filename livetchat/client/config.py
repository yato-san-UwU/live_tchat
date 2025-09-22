# livetchat/client/config.py
from pathlib import Path
import json, os

# ↩️ mets l'IP/port de TON serveur
API_BASE = os.environ.get("LTCHAT_API_BASE", "lien serveur + port")
WS_URL   = os.environ.get("LTCHAT_WS_URL") or (API_BASE.replace("http", "ws", 1).rstrip("/") + "/ws")

CONFIG_PATH = Path.home() / ".tchat_config.json"

def load_username_from_config() -> str:
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("username"), str):
                return data["username"][:32] or "guest"
    except Exception:
        pass
    return "guest"

def save_username_to_config(username: str) -> None:
    try:
        payload = {"username": (username or "guest")[:32]}
        CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
