from tkinter import Toplevel, Canvas

def _create_topmost(root, w, h, x, y):
    top = Toplevel(root)
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    top.geometry(f"{w}x{h}+{x}+{y}")
    return top

def _measure_text_height(root, text, font, width):
    """Calcule la hauteur nécessaire pour le texte avec la largeur donnée."""
    tmp = Toplevel(root); tmp.withdraw()
    c = Canvas(tmp, width=width, height=10, bg="black", highlightthickness=0)
    tid = c.create_text(width//2, 0, text=text, font=font, fill="white", anchor="n", width=width)
    bbox = c.bbox(tid) if c.bbox(tid) else (0,0,width,20)
    tmp.destroy()
    return (bbox[3]-bbox[1]) + 16  # padding

def show_overlay_username_top_left(root, username: str, seconds: float):
    if not username: return
    # Mesure largeur/hauteur du tag (police plus grande)
    screen_w = root.winfo_screenwidth()
    font = ("Arial", 24, "bold")
    w = min(360, int(screen_w * 0.6))
    h = _measure_text_height(root, username, font, w)
    x, y = 16, 16
    top = _create_topmost(root, w, h, x, y)
    c = Canvas(top, width=w, height=h, bg="black", highlightthickness=0); c.pack(fill="both", expand=True)
    c.create_text(w//2, h//2, text=username, font=font, fill="white", anchor="center")
    top.after(int(seconds * 1000), top.destroy)

def show_overlay_text_bottom(root, text: str, seconds: float):
    """Affiche un bandeau texte en bas de l'écran (pour l'audio notamment)."""
    if not text: return
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    max_w = int(screen_w * 0.9)
    font = ("Arial", 32, "bold")
    h = _measure_text_height(root, text, font, max_w)
    w = max_w
    x = (screen_w - w) // 2
    y = screen_h - h - 40
    top = _create_topmost(root, w, h, x, y)
    c = Canvas(top, width=w, height=h, bg="black", highlightthickness=0); c.pack(fill="both", expand=True)
    c.create_text(w//2, h//2, text=text, font=font, fill="white", anchor="center", width=w-16)
    top.after(int(seconds * 1000), top.destroy)
