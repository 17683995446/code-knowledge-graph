"""
WebSocket Manager - WebSocket连接管理
管理所有活跃的WebSocket连接，支持广播推送
"""

import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocket连接管理器
    支持广播消息到所有连接的客户端
    """

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """接受新的WebSocket连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket客户端已连接，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket客户端已断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息到所有连接的客户端"""
        if not self.active_connections:
            return
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        self.active_connections -= dead_connections

    async def send_update_notification(self, updated_files: list, errors: list):
        """发送文件更新通知"""
        await self.broadcast({
            "type": "file_update",
            "data": {
                "updated_files": updated_files,
                "errors": errors,
                "timestamp": __import__("datetime").datetime.now().isoformat()
            }
        })

    async def send_stats_update(self, stats: dict):
        """发送统计信息更新"""
        await self.broadcast({
            "type": "stats_update",
            "data": stats
        })
