import json, threading, tempfile
from tkinter import Tk, Label, Button, Entry, StringVar, filedialog, messagebox
from pathlib import Path

import requests, websocket

from livetchat.shared.version import VERSION
from livetchat.client.config import load_username_from_config, save_username_to_config, WS_URL, API_BASE
from livetchat.client.overlays import show_overlay_username_top_left, show_overlay_text_bottom
from livetchat.client.media import show_image_with_caption, play_video_overlay, play_audio_tempfile

ALLOWED_IMG_EXT = {".jpg", ".jpeg", ".png", ".gif"}
ALLOWED_VIDEO_EXT = {".mp4"}
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a"}

def main():
    root = Tk()
    root.title("Live Overlay — HTTP upload + WS notif")

    username = StringVar(value=load_username_from_config())
    display_time = StringVar(value="3")
    display_text = StringVar(value="")
    path_var = StringVar(value="")
    status_var = StringVar(value="Prêt.")

    Label(root, text="Pseudo:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
    Entry(root, textvariable=username, width=24).grid(row=0, column=1, sticky="w", padx=6, pady=6)
    Button(root, text="Enregistrer pseudo",
           command=lambda: (save_username_to_config(username.get().strip()),
                            messagebox.showinfo("Info","Pseudo enregistré.")))\
        .grid(row=0, column=2, sticky="w", padx=6, pady=6)

    Label(root, text="Durée (s):").grid(row=1, column=0, sticky="e", padx=6, pady=6)
    Entry(root, textvariable=display_time, width=10).grid(row=1, column=1, sticky="w", padx=6, pady=6)

    Label(root, text="Texte:").grid(row=2, column=0, sticky="e", padx=6, pady=6)
    Entry(root, textvariable=display_text, width=40).grid(row=2, column=1, columnspan=2, sticky="we", padx=6, pady=6)

    Label(root, text="Fichier (image/vidéo/audio):").grid(row=3, column=0, sticky="e", padx=6, pady=6)
    Entry(root, textvariable=path_var, width=40).grid(row=3, column=1, sticky="we", padx=6, pady=6)
    Button(root, text="Parcourir…", command=lambda: _browse(path_var)).grid(row=3, column=2, sticky="w", padx=6, pady=6)

    Button(root, text="Envoyer",
           command=lambda: _send_via_http(root, username, display_time, display_text, path_var, status_var))\
        .grid(row=4, column=0, columnspan=3, padx=6, pady=10, sticky="we")

    Label(root, textvariable=status_var, fg="gray").grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=6)

    from livetchat.client.updater import check_update
    Button(root, text="Vérifier mise à jour", command=lambda: check_update(VERSION))\
        .grid(row=6, column=0, columnspan=3, padx=6, pady=8, sticky="we")

    # Thread WS -> réception des notifications et affichage
    threading.Thread(target=_ws_listen, args=(root, status_var), daemon=True).start()

    root.mainloop()

def _browse(path_var):
    path = filedialog.askopenfilename(
        title="Choisir un fichier (image/vidéo/audio)",
        filetypes=[
            ("Images/MP4/Audio", "*.jpg;*.jpeg;*.png;*.gif;*.mp4;*.mp3;*.wav;*.ogg;*.m4a"),
            ("Images","*.jpg;*.jpeg;*.png;*.gif"),
            ("MP4","*.mp4"),
            ("Audio","*.mp3;*.wav;*.ogg;*.m4a"),
        ],
    )
    if path: path_var.set(path)

def _send_via_http(root, username_var, display_time_var, display_text_var, path_var, status_var):
    path = (path_var.get() or "").strip()
    if not path:
        messagebox.showwarning("Fichier manquant", "Choisis un fichier."); return
    p = Path(path)
    if not p.exists() or not p.is_file():
        messagebox.showerror("Erreur", "Chemin invalide."); return

    # durée + meta
    try: dt = float(display_time_var.get() or "0")
    except: dt = 0.0
    if dt <= 0: dt = 3.0
    uname = (username_var.get() or "guest").strip()
    save_username_to_config(uname)
    dtext = display_text_var.get() or ""

    # upload HTTP (comme avant)
    status_var.set("Upload…")
    try:
        with open(p, "rb") as f:
            files = {"file": (p.name, f)}
            data  = {"display_time": str(dt), "display_text": dtext, "username": uname}
            r = requests.post(f"{API_BASE}/upload/", files=files, data=data, timeout=60)
        if r.ok:
            info = r.json()
            status_var.set(f"✅ Envoyé: {info.get('filename','?')} ({info.get('kind','?')})")
        else:
            status_var.set(f"❌ Upload échoué ({r.status_code})")
    except Exception as e:
        status_var.set(f"❌ Upload erreur: {e}")

def _ws_listen(root, status_var):
    def on_message(ws, msg):
        try:
            obj = json.loads(msg)
        except Exception:
            return
        if obj.get("type") != "media_notice":
            return
        kind = obj.get("kind")
        filename = obj.get("filename")
        dt = float(obj.get("display_time", 3))
        dtext = obj.get("display_text", "")
        uname = obj.get("username", "guest")

        status_var.set(f"📩 {kind} de {uname}: {filename}")

        # Télécharger le média en HTTP puis afficher (image/vidéo avec légende intégrée)
        try:
            if kind == "image":
                r = requests.get(f"{API_BASE}/files/images/{filename}", timeout=60)
                if r.ok:
                    root.after(0, show_image_with_caption, root, r.content, dt, dtext)
            elif kind == "video":
                r = requests.get(f"{API_BASE}/files/videos/{filename}", timeout=60)
                if r.ok:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                        tmp.write(r.content); temp_path = tmp.name
                    root.after(0, play_video_overlay, root, temp_path, dt, dtext)
            elif kind == "audio":
                r = requests.get(f"{API_BASE}/files/audios/{filename}", timeout=60)
                if r.ok:
                    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".mp3"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(r.content); temp_path = tmp.name
                    threading.Thread(target=play_audio_tempfile, args=(temp_path, dt), daemon=True).start()
        except Exception as e:
            status_var.set(f"❌ Download erreur: {e}")

        # Pseudo en haut-gauche pour tout
        root.after(150, show_overlay_username_top_left, root, f"{uname}", dt)

        # Bandeau bas uniquement pour l'audio (image/vidéo ont déjà la légende dans la même fenêtre)
        if kind == "audio" and dtext:
            root.after(180, show_overlay_text_bottom, root, dtext, dt)

    def on_open(_):   status_var.set("WS connecté")
    def on_error(_,e):status_var.set(f"WS erreur: {e}")
    def on_close(*_): status_var.set("WS déconnecté — reconnexion…")

    while True:
        try:
            ws = websocket.WebSocketApp(WS_URL, on_message=on_message, on_open=on_open, on_error=on_error, on_close=on_close)
            ws.run_forever()
        except Exception as e:
            status_var.set(f"WS down: {e}")
        import time; time.sleep(2)
