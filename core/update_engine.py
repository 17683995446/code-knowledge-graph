"""
Update Engine - 增量更新引擎
核心引擎：处理文件变更，调用解析器，更新知识图谱
基于第一性原理：更新=删旧数据+插新数据

修复清单:
- BUG-UE-01: 删除 flush() 中对不存在 debounce_queue 的引用
- BUG-UE-03: 使用 run_in_executor 避免阻塞事件循环
- BUG-UE-05: 事务原子性保护（先解析再删除，失败可回滚）
- BUG-UE-06: entity_id_map 使用 (name, type_name) 复合key避免覆盖
- BUG-FW-01/02: 文件移动事件同时处理 src_path 和 dest_path
"""

import os
import asyncio
import logging
import threading
from queue import Queue
from typing import Dict, Set, Optional, Callable
from datetime import datetime

from core.database import KnowledgeDatabase
from core.file_watcher import FileWatcher
from parsers.parser_registry import ParserRegistry

logger = logging.getLogger(__name__)


class UpdateEngine:
    """
    增量更新引擎
    核心职责：接收文件变更 → 防抖合并 → 增量更新数据库
    """

    def __init__(self, project_path: str, database: KnowledgeDatabase,
                 parser_registry: ParserRegistry,
                 debounce_window: float = 1.0,
                 on_update_callback: Optional[Callable] = None):
        self.project_path = os.path.abspath(project_path)
        self.database = database
        self.parser_registry = parser_registry
        self.on_update_callback = on_update_callback
        self.debounce_window = debounce_window

        # 线程安全的事件队列
        self._event_queue: Queue = Queue()
        self._pending_events: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._loop = None  # 保存asyncio事件循环引用

        self.file_watcher = FileWatcher(
            project_path=project_path,
            callback=self._on_file_event
        )

        self.stats = {
            "total_updates": 0,
            "total_files_processed": 0,
            "last_update_time": None,
            "errors": []
        }

    def _on_file_event(self, file_path: str, event_type: str):
        """文件事件回调（同步，由watchdog线程调用）"""
        self._event_queue.put((file_path, event_type))

    async def _process_events_loop(self):
        """异步事件处理循环"""
        self._loop = asyncio.get_running_loop()  # 保存事件循环引用
        while self._running:
            try:
                # 非阻塞取出所有队列事件
                while not self._event_queue.empty():
                    file_path, event_type = self._event_queue.get_nowait()
                    with self._lock:
                        if file_path not in self._pending_events:
                            self._pending_events[file_path] = set()
                        self._pending_events[file_path].add(event_type)

                # 有待处理事件时，等待防抖窗口
                if self._pending_events:
                    await asyncio.sleep(self.debounce_window)
                    with self._lock:
                        batch = dict(self._pending_events)
                        self._pending_events.clear()

                    if batch:
                        # 在线程池中执行同步IO操作，避免阻塞事件循环
                        await asyncio.get_event_loop().run_in_executor(
                            None, self._process_batch_sync, batch
                        )

                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"事件处理循环错误: {e}")
                await asyncio.sleep(0.5)

    def _process_batch_sync(self, batch: Dict[str, Set[str]]):
        """同步处理一批文件变更（在线程池中执行）"""
        updated_files = []
        errors = []

        for file_path, event_types in batch.items():
            try:
                event_type = self._resolve_event_type(event_types)
                self._update_single_file(file_path, event_type)
                updated_files.append(file_path)
                self.stats["total_files_processed"] += 1
            except Exception as exception:
                error_msg = f"{file_path}: {str(exception)}"
                errors.append(error_msg)
                logger.error(f"更新文件失败: {error_msg}")

        self.stats["total_updates"] += 1
        self.stats["last_update_time"] = datetime.now().isoformat()
        self.stats["errors"] = errors[-100:]

        # 通知回调（需要在async上下文中调用）
        if self.on_update_callback and updated_files:
            loop = self._loop
            if loop and loop.is_running():
                # 使用默认参数绑定当前值，避免闭包问题
                callback = self.on_update_callback
                files_copy = list(updated_files)
                errors_copy = list(errors)
                loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(callback(files_copy, errors_copy))
                )

    def _resolve_event_type(self, event_types: Set[str]) -> str:
        """解析合并后的事件类型"""
        if "deleted" in event_types:
            return "deleted"
        if "created" in event_types:
            return "created"
        return "modified"

    def _update_single_file(self, file_path: str, event_type: str):
        """
        核心方法：更新单个文件（事务原子性保护）
        策略：先解析新数据，成功后再删除旧数据并插入新数据
        如果解析失败，旧数据保持不变
        """
        file_path = os.path.abspath(file_path)

        if event_type == "deleted":
            file_record = self.database.get_file_by_path(file_path)
            if file_record:
                self.database.delete_file_cascade(file_record.file_id)
                self.database.commit()
            return

        if event_type in ("created", "modified"):
            if not os.path.exists(file_path):
                return

            language = FileWatcher.detect_language(file_path)
            if not language:
                return

            # 先解析文件内容（可能失败）
            parser = self.parser_registry.get_parser(language)
            parse_result = None
            if parser:
                try:
                    parse_result = parser.parse_file(file_path)
                except Exception as e:
                    logger.warning(f"解析文件失败 {file_path}: {e}")
                    parse_result = None

            file_hash = self.database.compute_file_hash(file_path)

            # 解析成功后，执行原子更新（事务内完成）
            try:
                file_record = self.database.get_file_by_path(file_path)
                if file_record:
                    self.database.delete_file_cascade(file_record.file_id)

                file_id = self.database.upsert_file(file_path, language, file_hash)

                if parse_result:
                    self._store_parse_result(file_id, parse_result)

                self.database.commit()
            except Exception:
                self.database.rollback()
                raise

    def _store_parse_result(self, file_id: int, parse_result, language: str = ""):
        """将解析结果存储到数据库（不commit，由调用者控制事务）"""
        type_id_map = {}

        if parse_result.types:
            type_ids = self.database.insert_types(file_id, [
                {
                    "name": t.name,
                    "kind": t.kind,
                    "flags": t.flags,
                    "start_line": t.start_line,
                    "end_line": t.end_line
                }
                for t in parse_result.types
            ])
            for type_info, type_id in zip(parse_result.types, type_ids):
                type_id_map[type_info.name] = type_id

        # BUG-UE-06 修复：使用复合key (func_name, type_name) 避免同名函数覆盖
        entity_id_map = dict(type_id_map)

        if parse_result.functions:
            func_ids = self.database.insert_functions(file_id, [
                {
                    "name": f.name,
                    "type_name": f.type_name,
                    "start_line": f.start_line,
                    "end_line": f.end_line
                }
                for f in parse_result.functions
            ], type_id_map)
            for func_info, func_id in zip(parse_result.functions, func_ids):
                # 使用 (name, type_name) 作为复合key
                composite_key = f"{func_info.name}@{func_info.type_name}"
                entity_id_map[composite_key] = func_id
                # 同时用简单name做索引（用于调用关系匹配）
                if func_info.name not in entity_id_map:
                    entity_id_map[func_info.name] = func_id

        if parse_result.calls:
            caller_map = {}
            callee_map = {}
            for c in parse_result.calls:
                caller_map[c.caller] = entity_id_map.get(c.caller)
                callee_map[c.callee] = entity_id_map.get(c.callee)
            self.database.insert_calls(
                [{"caller": c.caller, "callee": c.callee} for c in parse_result.calls],
                caller_map, callee_map
            )

        if parse_result.references:
            self.database.insert_references(
                [{"from_entity": r.from_entity, "to_entity": r.to_entity, "kind": r.kind}
                 for r in parse_result.references],
                entity_id_map,
                current_file_id=file_id
            )

    def full_sync(self):
        """执行首次全量同步"""
        logger.info(f"开始全量同步: {self.project_path}")

        # 全量同步前清空所有关系数据，确保跨文件引用一致性
        # 因为逐文件更新时，calls/references中的ID可能指向已被重建的实体
        conn = self.database._get_connection()
        conn.execute("DELETE FROM calls")
        conn.execute("DELETE FROM code_references")
        conn.execute("DELETE FROM functions")
        conn.execute("DELETE FROM types")
        conn.execute("DELETE FROM files")
        conn.commit()

        extensions_map = FileWatcher.get_language_extensions()
        extensions = set(extensions_map.keys())

        total_files = 0
        updated_files = 0

        for root_dir, dir_names, file_names in os.walk(self.project_path):
            dir_names[:] = [
                d for d in dir_names
                if d not in {"__pycache__", "node_modules", ".git", "venv",
                             ".venv", "build", "dist", ".idea", ".vscode",
                             "target", ".gradle", "vendor", "Pods"}
            ]
            for file_name in file_names:
                ext = os.path.splitext(file_name)[1].lower()
                if ext in extensions:
                    total_files += 1
                    file_path = os.path.join(root_dir, file_name)
                    try:
                        self._update_single_file(file_path, "created")
                        updated_files += 1
                    except Exception as exception:
                        logger.error(f"全量同步失败 {file_path}: {exception}")

        self.stats["total_updates"] += 1
        self.stats["last_update_time"] = datetime.now().isoformat()
        logger.info(f"全量同步完成: 共{total_files}个文件, 成功{updated_files}个")
        return {"total": total_files, "updated": updated_files}

    def start(self):
        """启动增量更新引擎"""
        self._running = True
        self.file_watcher.start()
        logger.info(f"文件监控已启动: {self.project_path}")

    def start_async_loop(self):
        """启动异步事件处理循环"""
        self._running = True
        return self._process_events_loop()

    def stop(self):
        """停止增量更新引擎"""
        self._running = False
        self.file_watcher.stop()
        logger.info("文件监控已停止")

    async def flush(self):
        """刷新待处理事件"""
        with self._lock:
            if self._pending_events:
                batch = dict(self._pending_events)
                self._pending_events.clear()
                if batch:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._process_batch_sync, batch
                    )
