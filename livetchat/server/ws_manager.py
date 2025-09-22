import asyncio, json
from fastapi import WebSocket

class ConnectionManager:

    def __init__(self):
        self.active = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.add(ws)
        peer = f"{getattr(ws.client, 'host', '?')}:{getattr(ws.client, 'port', '?')}"
        print(f"[WS] connect {peer} — now {len(self.active)} client(s)")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self.active:
                self.active.remove(ws)
        peer = f"{getattr(ws.client, 'host', '?')}:{getattr(ws.client, 'port', '?')}"
        print(f"[WS] disconnect {peer} — now {len(self.active)} client(s)")

    async def broadcast_json(self, message, exclude=None):
        import asyncio
        payload = json.dumps(message)
        conns = list(self.active)
        tasks = []
        for w in conns:
            if exclude and w in exclude: continue
            tasks.append((w, asyncio.create_task(w.send_text(payload))))
        results = await asyncio.gather(*(t for _, t in tasks), return_exceptions=True)
        for (w,_), res in zip(tasks, results):
            if isinstance(res, Exception):
                print("[WS] send_text failed -> disconnecting:", res)
                await self.disconnect(w)

    async def broadcast_bytes(self, data, exclude=None):
        import asyncio
        conns = list(self.active); tasks = []
        for w in conns:
            if exclude and w in exclude: continue
            tasks.append((w, asyncio.create_task(w.send_bytes(data))))
        results = await asyncio.gather(*(t for _, t in tasks), return_exceptions=True)
        for (w,_), res in zip(tasks, results):
            if isinstance(res, Exception):
                await self.disconnect(w)
                
    def receivers_count(self, exclude=None):
        if exclude: return max(0, len(self.active)-len(exclude))
        return len(self.active)
