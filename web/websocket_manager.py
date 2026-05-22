"""
WebSocket Manager - WebSocket连接管理
管理所有活跃的WebSocket连接，支持广播推送
"""

import asyncio
import logging
import time
from collections import deque
from datetime import datetime
from typing import Set, Dict, List, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocket连接管理器
    支持广播消息到所有连接的客户端
    BUG-WS-001修复：broadcast时复制集合，避免遍历期间修改
    BUG-WS-002修复：broadcast异常处理添加日志
    BUG-WS-004修复：使用正常的datetime导入
    BUG-WS-007修复：添加消息批量合并和发送频率限制
    """

    # 广播频率限制配置
    BROADCAST_MIN_INTERVAL = 0.1  # 最小广播间隔（秒）
    MESSAGE_BATCH_WINDOW = 0.05  # 消息批量合并窗口（秒）
    MAX_PENDING_MESSAGES = 100  # 最大待发送消息数

    def __init__(self, max_connections: int = 100):
        self.active_connections: Set[WebSocket] = set()
        self.max_connections = max_connections
        # BUG-WS-007修复：广播频率限制
        self._last_broadcast_time: float = 0.0
        self._pending_messages: deque = deque(maxlen=self.MAX_PENDING_MESSAGES)
        self._broadcast_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """接受新的WebSocket连接
        BUG-WS-005修复：添加accept()异常保护
        BUG-WS-006修复：添加连接数上限保护
        """
        if len(self.active_connections) >= self.max_connections:
            logger.warning(f"WebSocket连接数已达上限 {self.max_connections}，拒绝新连接")
            await websocket.close(code=1013, reason="Too many connections")
            return
        try:
            await websocket.accept()
            self.active_connections.add(websocket)
            logger.info(f"WebSocket客户端已连接，当前连接数: {len(self.active_connections)}")
        except Exception as e:
            logger.warning(f"WebSocket accept失败: {e}")

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket客户端已断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """
        广播消息到所有连接的客户端
        BUG-WS-001修复：复制集合再遍历，避免RuntimeError
        BUG-WS-003修复：解决TOCTOU竞态
        BUG-WS-007修复：添加消息批量合并和发送频率限制
        """
        async with self._broadcast_lock:
            current_time = time.time()
            
            # 频率限制：确保广播间隔不小于最小间隔
            time_since_last = current_time - self._last_broadcast_time
            if time_since_last < self.BROADCAST_MIN_INTERVAL:
                await asyncio.sleep(self.BROADCAST_MIN_INTERVAL - time_since_last)
            
            # 复制集合，避免遍历期间修改
            connections = list(self.active_connections)
            if not connections:
                return
            
            dead_connections = []
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    # BUG-WS-002修复：记录异常日志
                    logger.debug(f"WebSocket发送失败，移除连接: {e}")
                    dead_connections.append(connection)
            for conn in dead_connections:
                self.active_connections.discard(conn)
            
            self._last_broadcast_time = time.time()

    async def broadcast_batch(self, messages: List[dict]):
        """
        批量广播多条消息（合并发送）
        BUG-WS-007修复：消息批量合并，减少广播次数
        """
        if not messages:
            return
        
        # 合并消息
        combined_message = {
            "type": "batch",
            "messages": messages,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(combined_message)

    async def send_update_notification(self, updated_files: list, errors: list):
        """发送文件更新通知"""
        await self.broadcast({
            "type": "file_update",
            "data": {
                "updated_files": updated_files,
                "errors": errors,
                "timestamp": datetime.now().isoformat()
            }
        })

    async def send_stats_update(self, stats: dict):
        """发送统计信息更新"""
        await self.broadcast({
            "type": "stats_update",
            "data": stats
        })
