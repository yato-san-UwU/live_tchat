import os, sys, hashlib, tempfile, subprocess
import requests
from tkinter import messagebox
from livetchat.client.config import API_BASE

def check_update(current_version: str):
    try:
        r = requests.get(f"{API_BASE}/manifest.json", timeout=10)
        r.raise_for_status()
        m = r.json(); latest = m.get("version"); url = m.get("url"); sha = m.get("sha256")
        if not latest or not url or not sha:
            messagebox.showwarning("Mise à jour", "Manifest incomplet."); return
        if latest == current_version:
            messagebox.showinfo("À jour", f"Version {current_version}"); return
        if not messagebox.askyesno("Mise à jour disponible", f"Version actuelle: {current_version}\nNouvelle version: {latest}\n\nInstaller maintenant ?"):
            return
        _perform_update(url, sha)
    except Exception as e:
        messagebox.showwarning("Mise à jour", f"Impossible de vérifier: {e}")
        
def _perform_update(url, sha256_hex):
    tmp_dir = tempfile.gettempdir()
    new_path = os.path.join(tmp_dir, "TchatLive.new.exe")
    bat_path = os.path.join(tmp_dir, "tchat_update.bat")
    try:
        h = hashlib.sha256()
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(new_path, "wb") as f:
                for chunk in r.iter_content(128 * 1024):
                    if not chunk: continue
                    f.write(chunk); h.update(chunk)
        if h.hexdigest().lower() != sha256_hex.lower():
            try: os.remove(new_path)
            except: pass
            messagebox.showerror("MAJ", "Hash invalide, mise à jour annulée."); return
    except Exception as e:
        messagebox.showerror("MAJ", f"Téléchargement impossible: {e}"); return
    batch = (
        '@echo off\n'
        'setlocal enabledelayedexpansion\n'
        'set TARGET="%~1"\n'
        'set NEW="%~2"\n'
        'set RETRIES=60\n'
        ':waitclose\n'
        '>nul 2>&1 (copy /b NUL %TARGET%)\n'
        'if errorlevel 1 (\n'
        '  timeout /t 1 >nul\n'
        '  set /a RETRIES-=1\n'
        '  if !RETRIES! GTR 0 goto waitclose\n'
        '  exit /b 1\n'
        ')\n'
        'del /f /q %TARGET% >nul 2>&1\n'
        'move /y %NEW% %TARGET%\n'
        'start "" %TARGET%\n'
        'del "%~f0"\n'
    )
    try:
        with open(bat_path, "w", encoding="utf-8") as f: f.write(batch)
    except Exception as e:
        messagebox.showerror("MAJ", f"Erreur d'écriture du script: {e}"); return
    target = sys.executable
    try:
        subprocess.Popen(["cmd", "/c", bat_path, target, new_path], close_fds=True)
    except Exception as e:
        messagebox.showerror("MAJ", f"Lancement de la mise à jour impossible: {e}"); return
    os._exit(0)
