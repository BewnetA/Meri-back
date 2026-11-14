import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Maps conversation_id or ticket_id -> list of active WebSockets
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        logger.info(
            f"WebSocket connected to room {room_id}. Total: {len(self.active_connections[room_id])}"
        )

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        logger.info(f"WebSocket disconnected from room {room_id}")

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.active_connections:
            data_str = json.dumps(message)
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_text(data_str)
                except Exception as e:
                    logger.error(f"Error broadcasting message to socket: {e}")


ws_manager = ConnectionManager()
