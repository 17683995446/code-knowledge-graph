"""
Web Package - Web服务模块
提供REST API和WebSocket实时推送
"""

from web.server import create_app
from web.websocket_manager import WebSocketManager

__all__ = ["create_app", "WebSocketManager"]
