"""
File Watcher - 跨平台文件监控
使用watchdog实现跨平台文件系统监控
修复: moved事件处理、TypeScript语言支持
"""

import os
import logging
from pathlib import Path
from typing import Callable, Set, Optional
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler, FileSystemEvent,
    FileSystemMovedEvent
)


logger = logging.getLogger(__name__)


class CodeFileHandler(FileSystemEventHandler):
    """代码文件变更事件处理器"""

    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "javascript",       # TypeScript由JavaScript解析器处理
        ".tsx": "javascript",      # TSX由JavaScript解析器处理
        ".java": "java",
        ".go": "go",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".rs": "rust",
        ".kt": "kotlin",
        ".swift": "swift",
        ".rb": "ruby",
        ".php": "php",
        ".ets": "arkts",
    }

    def __init__(self, callback: Callable, ignored_dirs: Optional[Set[str]] = None):
        super().__init__()
        self.callback = callback
        self.ignored_dirs = ignored_dirs or {
            "__pycache__", "node_modules", ".git", "venv",
            ".venv", "build", "dist", ".idea", ".vscode",
            "target", ".gradle", "vendor", "Pods"
        }

    def _should_ignore(self, path: str) -> bool:
        """检查路径是否应该被忽略"""
        path_parts = Path(path).parts
        return any(part in self.ignored_dirs for part in path_parts)

    def _is_code_file(self, path: str) -> bool:
        """检查是否是代码文件"""
        ext = Path(path).suffix.lower()
        return ext in self.LANGUAGE_EXTENSIONS

    def _dispatch_event(self, path: str, event_type: str):
        """统一事件分发"""
        if self._should_ignore(path):
            return
        if not self._is_code_file(path):
            return
        if event_type != "ignore":
            self.callback(path, event_type)

    def on_created(self, event: FileSystemEvent):
        try:
            if not event.is_directory:
                self._dispatch_event(event.src_path, "created")
        except Exception as e:
            logger.error(f"on_created事件处理异常: {e}")

    def on_deleted(self, event: FileSystemEvent):
        try:
            if not event.is_directory:
                self._dispatch_event(event.src_path, "deleted")
        except Exception as e:
            logger.error(f"on_deleted事件处理异常: {e}")

    def on_modified(self, event: FileSystemEvent):
        try:
            if not event.is_directory:
                self._dispatch_event(event.src_path, "modified")
        except Exception as e:
            logger.error(f"on_modified事件处理异常: {e}")

    def on_moved(self, event: FileSystemMovedEvent):
        """
        处理文件移动事件
        BUG-FW-01/02 修复：同时处理源路径（删除）和目标路径（创建）
        """
        if event.is_directory:
            return
        # 源路径：视为删除
        self._dispatch_event(event.src_path, "deleted")
        # 目标路径：视为创建（新位置需要重新索引）
        self._dispatch_event(event.dest_path, "created")


class FileWatcher:
    """
    跨平台文件监控器
    基于watchdog实现，支持所有主流操作系统
    """

    def __init__(self, project_path: str, callback: Callable,
                 ignored_dirs: Optional[Set[str]] = None):
        self.project_path = os.path.abspath(project_path)
        self.callback = callback
        self.observer = Observer()
        self.handler = CodeFileHandler(callback, ignored_dirs)

    def start(self):
        """启动文件监控"""
        self.observer.schedule(
            self.handler,
            self.project_path,
            recursive=True
        )
        self.observer.start()

    def stop(self):
        """停止文件监控"""
        self.observer.stop()
        self.observer.join(timeout=5)

    @staticmethod
    def get_language_extensions() -> dict:
        """获取支持的语言扩展名映射"""
        return CodeFileHandler.LANGUAGE_EXTENSIONS.copy()

    @staticmethod
    def detect_language(file_path: str) -> Optional[str]:
        """根据文件扩展名检测语言类型"""
        ext = Path(file_path).suffix.lower()
        return CodeFileHandler.LANGUAGE_EXTENSIONS.get(ext)
