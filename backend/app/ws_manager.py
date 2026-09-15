import asyncio
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._buffers: dict[str, list[dict]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections[session_id] = websocket
        for msg in self._buffers.get(session_id, []):
            await websocket.send_json(msg)

    def disconnect(self, session_id: str):
        self._connections.pop(session_id, None)

    async def send(self, session_id: str, message: dict):
        self._buffers.setdefault(session_id, []).append(message)
        ws = self._connections.get(session_id)
        if ws is not None:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(session_id)

    async def emit(self, session_id: str, stage: str, status: str, log: str, data: dict | None = None, delay: float = 0.4):
        await self.send(session_id, {"stage": stage, "status": status, "log": log, "data": data or {}})
        if delay:
            await asyncio.sleep(delay)


manager = ConnectionManager()
