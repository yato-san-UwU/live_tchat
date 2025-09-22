import json, threading, time
import websocket
from dataclasses import dataclass
import base64

@dataclass

class PendingEvent:
    kind: str
    event_id: str
    username: str
    display_time: float
    display_text: str
    content_type: str
    content_length: int
    start_after_ms: int
    server_ts_ms: int
    received_bytes: bytearray

class LiveClient:
    def __init__(self, ws_url: str, on_image, on_video, on_audio, on_status):
        self.ws_url = ws_url; self.ws = None; self.thread = None; self.alive = False
        self.pending = None
        self.on_image = on_image; self.on_video = on_video; self.on_audio = on_audio; self.on_status = on_status
        self._send_lock = threading.Lock(); self._pinger = None

    def connect(self):
        if self.thread and self.thread.is_alive(): return
        self.alive = True; self.thread = threading.Thread(target=self._run, daemon=True); self.thread.start()
        self._pinger = threading.Thread(target=self._ping_loop, daemon=True); self._pinger.start()

    def _ping_loop(self):
        while self.alive:
            try:
                if self.ws: self.ws.ping()
            except Exception: pass
            time.sleep(20)

    def _run(self):
        while self.alive:
            try:
                self.ws = websocket.WebSocket(); self.ws.connect(self.ws_url, timeout=5)
                self.on_status("Connecté au serveur.")
                while self.alive:
                    msg = self.ws.recv()
                    if isinstance(msg, bytes):
                        if self.pending is not None:
                            self.pending.received_bytes.extend(msg)
                            if len(self.pending.received_bytes) >= self.pending.content_length:
                                self._finalize_pending()
                    else:
                        try:
                            obj = json.loads(msg)
                        except Exception:
                            continue
                        mtype = obj.get("type")
                        if mtype in ("image_start", "video_start", "audio_start"):
                            kind = "image" if mtype == "image_start" else "video" if mtype == "video_start" else "audio"
                            self.pending = PendingEvent(
                                kind=kind,
                                event_id=obj.get("event_id", ""),
                                username=obj.get("username", ""),
                                display_time=float(obj.get("display_time", 3)),
                                display_text=obj.get("display_text", ""),
                                content_type=obj.get("content_type", "image/jpeg"),
                                content_length=int(obj.get("content_length", 0)),
                                start_after_ms=int(obj.get("start_after_ms", 1000)),
                                server_ts_ms=int(obj.get("server_ts_ms", 0)),
                                received_bytes=bytearray(),
                            )
                            self.pending._encoding = obj.get("encoding", "bin")
                            self.pending._meta_received_local_ms = int(time.time() * 1000)
                        elif mtype in ("image_chunk_b64", "video_chunk_b64", "audio_chunk_b64"):
                            if self.pending is not None:
                                b64 = obj.get("b64", "")
                                if b64:
                                    try:
                                        self.pending.received_bytes.extend(base64.b64decode(b64))
                                    except Exception:
                                        pass
                                # finalisation si on a tout reçu
                                if len(self.pending.received_bytes) >= self.pending.content_length:
                                    self._finalize_pending()
                        elif mtype in ("image_end", "video_end", "audio_end"):
                            if self.pending is not None:
                                self._finalize_pending()
                        elif mtype in ("image_ack", "video_ack", "audio_ack"):
                            b = obj.get("bytes", 0); ct = obj.get("content_type", "?")
                            self.on_status(f"✅ Envoyé ({ct}, {b} octets).")
                        elif mtype == "error":
                            self.on_status(f"❌ Erreur: {obj.get('error','?')}")
                        else:
                            pass
            except Exception:
                self.on_status("Déconnecté. Reconnexion…"); time.sleep(2.0)
            finally:
                try:
                    if self.ws: self.ws.close()
                except Exception: pass
                self.ws = None
                
    def _finalize_pending(self):
        if not self.pending: return
        p = self.pending; self.pending = None
        now_ms = int(time.time() * 1000)
        target_ms = getattr(p, "_target_ms", None)
        if target_ms is None: target_ms = p._meta_received_local_ms + p.start_after_ms
        delay = max(0.0, (target_ms - now_ms) / 1000.0)
        data = bytes(p.received_bytes)
        import threading
        if p.kind == "image":
            threading.Thread(target=self.on_image, args=(p, data, delay), daemon=True).start()
        elif p.kind == "video":
            threading.Thread(target=self.on_video, args=(p, data, delay), daemon=True).start()
        else:
            threading.Thread(target=self.on_audio, args=(p, data, delay), daemon=True).start()

    def send_image(self, username, display_time, display_text, img_bytes, content_type):
        if not self.ws: raise RuntimeError("WebSocket non connecté.")
        meta = {"type":"image_meta","username":username,"display_time":float(display_time),"display_text":display_text,"content_type":content_type}
        with self._send_lock:
            self.on_status("Envoi image…"); self.ws.send(json.dumps(meta)); self.ws.send(img_bytes)

    def send_video(self, username, display_time, display_text, video_bytes, content_type):
        if not self.ws: raise RuntimeError("WebSocket non connecté.")
        meta = {"type":"video_meta","username":username,"display_time":float(display_time),"display_text":display_text,"content_type":content_type}
        with self._send_lock:
            self.on_status("Envoi vidéo…"); self.ws.send(json.dumps(meta)); self.ws.send(video_bytes)

    def send_audio(self, username, display_time, display_text, audio_bytes, content_type):
        if not self.ws: raise RuntimeError("WebSocket non connecté.")
        meta = {"type":"audio_meta","username":username,"display_time":float(display_time),"display_text":display_text,"content_type":content_type}
        with self._send_lock:
            self.on_status("Envoi audio…"); self.ws.send(json.dumps(meta)); self.ws.send(audio_bytes)

    def close(self): self.alive = False
