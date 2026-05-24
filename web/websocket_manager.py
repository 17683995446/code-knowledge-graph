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
    BUG-WS-09修复：添加消息大小限制（默认1MB）
    BUG-WS-11修复：添加心跳超时检测机制
    """

    # 广播频率限制配置
    BROADCAST_MIN_INTERVAL = 0.1  # 最小广播间隔（秒）
    MESSAGE_BATCH_WINDOW = 0.05  # 消息批量合并窗口（秒）
    MAX_PENDING_MESSAGES = 100  # 最大待发送消息数
    MAX_MESSAGE_SIZE = 1024 * 1024  # BUG-WS-09: 最大消息大小（1MB）
    HEARTBEAT_TIMEOUT = 60.0  # BUG-WS-11: 心跳超时时间（秒）
    HEARTBEAT_CHECK_INTERVAL = 30.0  # BUG-WS-11: 心跳检查间隔（秒）

    def __init__(self, max_connections: int = 100):
        self.active_connections: Set[WebSocket] = set()
        self.max_connections = max_connections
        # BUG-WS-007修复：广播频率限制
        self._last_broadcast_time: float = 0.0
        self._pending_messages: deque = deque(maxlen=self.MAX_PENDING_MESSAGES)
        self._broadcast_lock = asyncio.Lock()
        # BUG-WS-11修复：心跳超时检测
        self._connection_last_active: Dict[WebSocket, float] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        """接受新的WebSocket连接
        BUG-WS-005修复：添加accept()异常保护
        BUG-WS-006修复：添加连接数上限保护
        BUG-WS-11修复：记录连接活跃时间
        BUG-WS-LOCK-01修复：使用锁保护active_connections集合操作
        """
        async with self._broadcast_lock:
            if len(self.active_connections) >= self.max_connections:
                logger.warning(f"WebSocket连接数已达上限 {self.max_connections}，拒绝新连接")
                try:
                    await websocket.close(code=1013, reason="Too many connections")
                except Exception:
                    pass
                return
        try:
            await websocket.accept()
            async with self._broadcast_lock:
                self.active_connections.add(websocket)
                # BUG-WS-11修复：记录连接活跃时间
                self._connection_last_active[websocket] = time.time()
            logger.info(f"WebSocket客户端已连接，当前连接数: {len(self.active_connections)}")
        except Exception as e:
            logger.warning(f"WebSocket accept失败: {e}")

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接
        BUG-WS-11修复：清理心跳记录
        BUG-WS-LOCK-01修复：注意disconnect是同步方法，使用discard是线程安全的
        """
        self.active_connections.discard(websocket)
        # BUG-WS-11修复：清理心跳记录
        if websocket in self._connection_last_active:
            del self._connection_last_active[websocket]
        logger.info(f"WebSocket客户端已断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """
        广播消息到所有连接的客户端
        BUG-WS-001修复：复制集合再遍历，避免RuntimeError
        BUG-WS-003修复：解决TOCTOU竞态
        BUG-WS-007修复：添加消息批量合并和发送频率限制
        BUG-WS-09修复：添加消息大小限制
        BUG-WS-11修复：更新连接活跃时间
        """
        # BUG-WS-09修复：检查消息大小
        import json
        try:
            message_size = len(json.dumps(message))
            if message_size > self.MAX_MESSAGE_SIZE:
                logger.warning(f"消息大小 {message_size} 超过限制 {self.MAX_MESSAGE_SIZE}，跳过发送")
                return
        except Exception as e:
            logger.warning(f"计算消息大小失败: {e}")

        # BUG-WS-BROADCAST-SLEEP-01修复：频率限制的sleep移到锁外面，避免持锁阻塞
        current_time = time.time()
        time_since_last = current_time - self._last_broadcast_time
        if time_since_last < self.BROADCAST_MIN_INTERVAL:
            await asyncio.sleep(self.BROADCAST_MIN_INTERVAL - time_since_last)

        async with self._broadcast_lock:
            
            # 复制集合，避免遍历期间修改
            connections = list(self.active_connections)
            if not connections:
                return
            
            dead_connections = []
            for connection in connections:
                try:
                    await connection.send_json(message)
                    # BUG-WS-11修复：更新连接活跃时间
                    self._connection_last_active[connection] = time.time()
                except Exception as e:
                    # BUG-WS-002修复：记录异常日志
                    logger.debug(f"WebSocket发送失败，移除连接: {e}")
                    dead_connections.append(connection)
            for conn in dead_connections:
                self.active_connections.discard(conn)
                # BUG-WS-11修复：清理心跳记录
                if conn in self._connection_last_active:
                    del self._connection_last_active[conn]
            
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
        """
        发送统计信息更新
        BUG-SVR-MEM-004修复：限制stats数据大小，防止大数据广播
        """
        # BUG-SVR-MEM-004修复：限制stats数据大小，只发送关键统计信息
        limited_stats = {
            "total_files": stats.get("total_files", 0),
            "total_types": stats.get("total_types", 0),
            "total_functions": stats.get("total_functions", 0),
            "total_calls": stats.get("total_calls", 0),
            "total_references": stats.get("total_references", 0),
            "languages": stats.get("languages", {}),
        }
        await self.broadcast({
            "type": "stats_update",
            "data": limited_stats
        })

    async def start_heartbeat_check(self):
        """
        BUG-WS-11修复：启动心跳超时检测任务
        定期检查连接活跃度，关闭超时的连接
        """
        self._heartbeat_task = asyncio.create_task(self._heartbeat_check_loop())
        logger.info("WebSocket心跳检测已启动")

    async def stop_heartbeat_check(self):
        """BUG-WS-11修复：停止心跳检测任务"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
            logger.info("WebSocket心跳检测已停止")

    async def _heartbeat_check_loop(self):
        """BUG-WS-11修复：心跳检测循环"""
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_CHECK_INTERVAL)
                await self._check_inactive_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳检测错误: {e}")

    async def _check_inactive_connections(self):
        """BUG-WS-11修复：检查并关闭不活跃的连接"""
        current_time = time.time()
        dead_connections = []

        for connection, last_active in list(self._connection_last_active.items()):
            if current_time - last_active > self.HEARTBEAT_TIMEOUT:
                logger.warning(f"WebSocket连接心跳超时，关闭连接")
                dead_connections.append(connection)

        for conn in dead_connections:
            try:
                await conn.close(code=1001, reason="Heartbeat timeout")
            except Exception:
                pass
            self.active_connections.discard(conn)
            if conn in self._connection_last_active:
                del self._connection_last_active[conn]

    def update_connection_activity(self, websocket: WebSocket):
        """BUG-WS-11修复：手动更新连接活跃时间（收到消息时调用）"""
        self._connection_last_active[websocket] = time.time()
