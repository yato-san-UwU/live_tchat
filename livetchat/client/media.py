import io, time, os, sys
from tkinter import Toplevel, Label, Canvas, Frame, messagebox
from PIL import Image, ImageTk, ImageSequence

try:
    import vlc
    VLC_AVAILABLE = True
except Exception:
    VLC_AVAILABLE = False


def _center_geometry(root, w, h):
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x = (sw - w)//2
    y = (sh - h)//2
    return f"{w}x{h}+{x}+{y}"


def show_image_with_caption(root, img_bytes: bytes, seconds: float, caption: str | None):
    """Image centrée + légende dessous (même fenêtre), texte non coupé."""
    try:
        image = Image.open(io.BytesIO(img_bytes))
    except Exception:
        messagebox.showerror("Erreur", "Image invalide reçue.")
        return

    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    max_w, max_h = int(sw * 0.9), int(sh * 0.9)

    font = ("Arial", 32, "bold")

    def _measure_caption_h(text, width):
        if not text:
            return 0
        tmp = Toplevel(root); tmp.withdraw()
        c = Canvas(tmp, width=width, height=10, bg="black", highlightthickness=0)
        tid = c.create_text(width//2, 0, text=text, font=font, fill="white",
                            anchor="n", width=width-16)
        bbox = c.bbox(tid) if c.bbox(tid) else (0, 0, width, 20)
        tmp.destroy()
        return (bbox[3] - bbox[1]) + 16  # padding

    is_gif = (getattr(image, "format", "") == "GIF") and getattr(image, "is_animated", False)
    if not is_gif:
        image.thumbnail((max_w, max_h))
        w, h = image.size
        cap_h = _measure_caption_h(caption, w) if caption else 0
        total_h = h + cap_h

        top = Toplevel(root)
        top.overrideredirect(True)
        top.geometry(_center_geometry(root, w, total_h))

        # amener devant puis relâcher (Alt+Tab possible)
        top.attributes("-topmost", True); top.lift(); top.focus_force()
        top.after(1200, lambda: top.attributes("-topmost", False))

        img_lbl = Label(top, bg="black")
        img_lbl.pack(fill="x")
        tk_img = ImageTk.PhotoImage(image)
        img_lbl.configure(image=tk_img)
        img_lbl.image = tk_img

        if caption:
            cap = Canvas(top, width=w, height=cap_h, bg="black", highlightthickness=0)
            cap.pack(fill="x")
            cap.create_text(w//2, cap_h//2, text=caption, font=font, fill="white",
                            anchor="center", width=w-16)

        top.after(int(seconds * 1000), top.destroy)
        return

    # GIF animé
    frames, durations = [], []
    for frame in ImageSequence.Iterator(image):
        fr = frame.convert("RGBA")
        fr.thumbnail((max_w, max_h))
        frames.append(ImageTk.PhotoImage(fr))
        durations.append(max(20, frame.info.get("duration", 100)))
    if not frames:
        return
    w, h = frames[0].width(), frames[0].height()
    cap_h = _measure_caption_h(caption, w) if caption else 0
    total_h = h + cap_h

    top = Toplevel(root)
    top.overrideredirect(True)
    top.geometry(_center_geometry(root, w, total_h))

    top.attributes("-topmost", True); top.lift(); top.focus_force()
    top.after(1200, lambda: top.attributes("-topmost", False))

    img_lbl = Label(top, bg="black"); img_lbl.pack(fill="x")
    if caption:
        cap = Canvas(top, width=w, height=cap_h, bg="black", highlightthickness=0)
        cap.pack(fill="x")
        cap.create_text(w//2, cap_h//2, text=caption, font=font, fill="white",
                        anchor="center", width=w-16)

    start = time.time()
    idx = {"i": 0}

    def animate():
        if time.time() - start >= seconds:
            try: top.destroy()
            except Exception: pass
            return
        i = idx["i"]
        img_lbl.configure(image=frames[i]); img_lbl.image = frames[i]
        idx["i"] = (i + 1) % len(frames)
        delay = durations[i] if i < len(durations) else 100
        top.after(delay, animate)

    animate()


def play_video_overlay(root, path: str, seconds: float, caption: str | None):
    """
    VLC intégré dans une fenêtre Tk (pop au premier plan, puis relâché).
    Pas d'events VLC (polling UI), cleanup idempotent,
    garde-fou basé sur la durée réelle + cap éventuel via `seconds`.
    """
    if not VLC_AVAILABLE:
        messagebox.showerror("VLC manquant", "Installe 'python-vlc' pour lire les vidéos.")
        return

    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    vid_w, vid_h = int(sw * 0.75), int(sh * 0.6)

    def _measure_caption_h(text, width):
        if not text:
            return 0
        tmp = Toplevel(root); tmp.withdraw()
        c = Canvas(tmp, width=width, height=10, bg="black", highlightthickness=0)
        tid = c.create_text(width//2, 0, text=text, font=("Arial", 28, "bold"),
                            fill="white", anchor="n", width=width-16)
        bbox = c.bbox(tid) if c.bbox(tid) else (0, 0, width, 20)
        tmp.destroy()
        return (bbox[3] - bbox[1]) + 12

    cap_h = _measure_caption_h(caption, vid_w) if caption else 0
    total_h = vid_h + cap_h

    top = Toplevel(root)
    top.overrideredirect(True)
    top.geometry(_center_geometry(root, vid_w, total_h))

    # amener devant puis relâcher (Alt+Tab possible)
    top.attributes("-topmost", True); top.lift(); top.focus_force()
    top.after(1200, lambda: top.attributes("-topmost", False))

    # zone vidéo
    video_frame = Frame(top, width=vid_w, height=vid_h, bg="black")
    video_frame.pack(fill="x")

    # légende
    if caption:
        cap = Canvas(top, width=vid_w, height=cap_h, bg="black", highlightthickness=0)
        cap.pack(fill="x")
        cap.create_text(vid_w//2, cap_h//2, text=caption, font=("Arial", 28, "bold"),
                        fill="white", anchor="center", width=vid_w-16)

    # VLC (sans --video-on-top)
    instance = vlc.Instance("--no-video-title-show")
    player = instance.media_player_new()
    media = instance.media_new(path)
    player.set_media(media)

    # injecter le rendu dans la frame
    try:
        hwnd = video_frame.winfo_id()
        if sys.platform.startswith("win"):
            player.set_hwnd(hwnd)
        elif sys.platform.startswith("linux"):
            player.set_xwindow(hwnd)
        elif sys.platform == "darwin":
            player.set_nsobject(hwnd)
    except Exception:
        pass

    state = {"closed": False}

    def _safe_remove(p):
        try:
            os.remove(p)
        except Exception:
            # re-tente un peu plus tard si besoin
            root.after(700, lambda: (os.path.exists(p) and _try_remove(p)))

    def _try_remove(p):
        try:
            os.remove(p)
        except Exception:
            pass

    def cleanup():
        if state["closed"]:
            return
        state["closed"] = True
        # stop + release VLC
        try: player.stop()
        except Exception: pass
        try: player.set_media(None)
        except Exception: pass
        try: player.release()
        except Exception: pass
        try: instance.release()
        except Exception: pass
        # close window
        try: top.destroy()
        except Exception: pass
        # supprime le fichier après un léger délai (handle libéré)
        root.after(300, lambda: (os.path.exists(path) and _safe_remove(path)))

    # fermer si l'utilisateur clique la croix
    try:
        top.protocol("WM_DELETE_WINDOW", lambda: root.after(0, cleanup))
    except Exception:
        pass

    # démarrer
    player.play()

    # -------- Durée réelle & garde-fou --------
    # On attend que VLC connaisse la durée (ms > 0). On cale le timeout sur min(durée+1s, seconds si fourni)
    dur_box = {"ms": -1, "tries": 0, "armed": False}

    def wait_duration():
        if state["closed"]:
            return
        try:
            ms = media.get_duration()  # en ms (peut valoir -1 au début)
        except Exception:
            ms = -1
        if ms and ms > 0:
            dur_box["ms"] = ms
            natural_limit = ms + 1000  # marge 1s après fin naturelle
            cap = int(max(0.1, seconds) * 1000) if seconds and seconds > 0 else None
            limit = min(natural_limit, cap) if cap else natural_limit
            if not dur_box["armed"]:
                dur_box["armed"] = True
                top.after(limit, cleanup)
        else:
            dur_box["tries"] += 1
            if dur_box["tries"] < 40:  # ~4s d'attente max
                root.after(100, wait_duration)
            else:
                # durée inconnue: fallback (3 min ou seconds si fourni)
                fallback = int((seconds if (seconds and seconds > 0) else 180) * 1000)
                if not dur_box["armed"]:
                    dur_box["armed"] = True
                    top.after(fallback, cleanup)

    root.after(120, wait_duration)
    # ------------------------------------------

    # Polling état VLC (évite les callbacks)
    def tick():
        if state["closed"]:
            return
        try:
            st = player.get_state()
        except Exception:
            cleanup(); return
        if str(st) in ("State.Ended", "State.Stopped", "State.Error"):
            cleanup(); return
        root.after(300, tick)

    root.after(350, tick)


def play_audio_tempfile(path: str, seconds: float):
    if not VLC_AVAILABLE:
        messagebox.showerror("VLC manquant", "Installe 'python-vlc' pour lire l'audio.")
        return
    player = vlc.MediaPlayer(path)
    player.play()
    time.sleep(max(0.1, seconds))
    try:
        player.stop()
    except Exception:
        pass
    try:
        os.remove(path)
    except Exception:
        pass
