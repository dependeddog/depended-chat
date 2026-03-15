from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._user_connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._chat_connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect_user(self, user_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._user_connections[user_id].add(websocket)

    async def disconnect_user(self, user_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._user_connections.get(user_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._user_connections.pop(user_id, None)

    async def connect_chat(self, chat_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._chat_connections[chat_id].add(websocket)

    async def disconnect_chat(self, chat_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._chat_connections.get(chat_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._chat_connections.pop(chat_id, None)

    async def send_to_user(self, user_id: UUID, payload: dict) -> None:
        async with self._lock:
            targets = list(self._user_connections.get(user_id, set()))

        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                connections = self._user_connections.get(user_id)
                if not connections:
                    return
                for websocket in stale:
                    connections.discard(websocket)
                if not connections:
                    self._user_connections.pop(user_id, None)

    async def broadcast_to_chat(self, chat_id: UUID, payload: dict) -> None:
        async with self._lock:
            targets = list(self._chat_connections.get(chat_id, set()))

        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                connections = self._chat_connections.get(chat_id)
                if not connections:
                    return
                for websocket in stale:
                    connections.discard(websocket)
                if not connections:
                    self._chat_connections.pop(chat_id, None)


ws_manager = ConnectionManager()
