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
        self._event_queue: Queue = Queue(maxsize=10000)  # BUG-UPDATE-005修复: 限制最大10000个事件
        self._pending_events: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()
        self._stats_lock = threading.Lock()  # BUG-UE-001修复: stats字典的并发访问保护
        # BUG-UPDATE-010/011修复: 使用threading.Event替代bool标志，确保原子操作
        self._running_event = threading.Event()
        self._running_event.set()  # 初始状态为运行
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
        while self._running_event.is_set():  # BUG-UPDATE-010/011修复: 使用Event检查
            try:
                # BUG-LOOP-01修复：使用try/except捕获queue.Empty，避免多线程下empty()不可靠
                while True:
                    try:
                        file_path, event_type = self._event_queue.get_nowait()
                    except Exception:
                        break  # 队列为空，退出内层循环
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
                        # BUG-LOOP-04修复：使用get_running_loop()替代已弃用的get_event_loop()
                        await asyncio.get_running_loop().run_in_executor(
                            None, self._process_batch_sync, batch
                        )

                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"事件处理循环错误: {e}")
                await asyncio.sleep(0.5)

    def _process_batch_sync(self, batch: Dict[str, Set[str]]):
        """同步处理一批文件变更（在线程池中执行）
        BUG-UPDATE-007修复: 每个文件处理独立隔离，一个失败不影响其他文件
        BUG-UE-001修复: 使用锁保护stats的读写操作
        """
        updated_files = []
        errors = []

        for file_path, event_types in batch.items():
            try:
                event_type = self._resolve_event_type(event_types)
                self._update_single_file(file_path, event_type)
                updated_files.append(file_path)
                with self._stats_lock:  # BUG-UE-001修复: 加锁保护stats
                    self.stats["total_files_processed"] += 1
            except Exception as exception:
                error_msg = f"{file_path}: {str(exception)}"
                errors.append(error_msg)
                logger.error(f"更新文件失败: {error_msg}")
                # BUG-UPDATE-007修复: 继续处理其他文件，不中断整个批处理

        with self._stats_lock:  # BUG-UE-001修复: 加锁保护stats
            self.stats["total_updates"] += 1
            self.stats["last_update_time"] = datetime.now().isoformat()
            self.stats["errors"] = errors[-100:]

        # 通知回调（需要在async上下文中调用）
        # BUG-UPDATE-015修复: 回调异常隔离
        if self.on_update_callback and updated_files:
            try:
                loop = self._loop
                if loop and loop.is_running():
                    # 使用默认参数绑定当前值，避免闭包问题
                    callback = self.on_update_callback
                    files_copy = list(updated_files)
                    errors_copy = list(errors)
                    loop.call_soon_threadsafe(
                        lambda: asyncio.ensure_future(callback(files_copy, errors_copy))
                    )
            except Exception as callback_error:
                # BUG-UPDATE-015修复: 捕获回调异常，不影响主流程
                logger.error(f"回调执行失败: {callback_error}")

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
        BUG-UE-007修复：实现"先解析后替换"策略，解析失败时保留旧数据
        """
        file_path = os.path.abspath(file_path)

        if event_type == "deleted":
            # BUG-SINGLE-01修复：添加异常保护，确保删除失败不导致整个批处理中断
            try:
                file_record = self.database.get_file_by_path(file_path)
                if file_record:
                    self.database.delete_file_cascade(file_record.file_id)
                    self.database.commit()
            except Exception as e:
                logger.error(f"删除文件失败 {file_path}: {e}")
                self.database.rollback()
            return

        if event_type in ("created", "modified"):
            if not os.path.exists(file_path):
                return

            language = FileWatcher.detect_language(file_path)
            if not language:
                return

            # BUG-UE-007修复：先解析文件内容，解析成功后再删除旧数据
            parser = self.parser_registry.get_parser(language)
            parse_result = None
            parse_success = False
            if parser:
                try:
                    parse_result = parser.parse_file(file_path)
                    parse_success = True
                except Exception as e:
                    logger.warning(f"解析文件失败 {file_path}: {e}，保留旧数据")
                    parse_result = None
                    parse_success = False

            file_hash = self.database.compute_file_hash(file_path)

            # BUG-UE-007修复：只有解析成功才执行更新，否则保留旧数据
            if not parse_success:
                # 解析失败，检查是否是新文件（无旧数据）
                file_record = self.database.get_file_by_path(file_path)
                if file_record is None:
                    # 新文件但解析失败，只插入文件记录，不存储解析结果
                    try:
                        file_id = self.database.upsert_file(file_path, language, file_hash)
                        self.database.commit()
                        logger.info(f"新文件解析失败，仅记录文件信息: {file_path}")
                    except Exception as e:
                        logger.error(f"插入文件记录失败 {file_path}: {e}")
                        self.database.rollback()
                # 有旧数据则保留不变
                return

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
            # BUG-STORE-06修复：不在此处commit，由调用者_update_single_file统一控制事务边界
            # 原commit()会破坏外层事务的rollback能力

    def full_sync(self):
        """
        执行首次全量同步
        BUG-FULL-SYNC-01修复：两阶段同步，确保跨文件引用能正确解析
        BUG-UE-004修复：使用临时表备份策略，防止崩溃后数据全部丢失
        BUG-UE-003修复：备份失败时中止同步
        BUG-UE-004修复：清空失败时抛出异常
        第一阶段：提取所有文件的实体（types/functions/calls）
        第二阶段：建立跨文件引用关系（references）
        """
        logger.info(f"开始全量同步: {self.project_path}")

        # BUG-UE-004修复：先将旧数据备份到临时表，成功后再删除
        conn = self.database._get_connection()
        backup_success = False
        try:
            # 创建备份临时表
            conn.execute("CREATE TABLE IF NOT EXISTS _backup_files AS SELECT * FROM files WHERE 0")
            conn.execute("DELETE FROM _backup_files")
            conn.execute("INSERT INTO _backup_files SELECT * FROM files")
            conn.execute("CREATE TABLE IF NOT EXISTS _backup_types AS SELECT * FROM types WHERE 0")
            conn.execute("DELETE FROM _backup_types")
            conn.execute("INSERT INTO _backup_types SELECT * FROM types")
            conn.execute("CREATE TABLE IF NOT EXISTS _backup_functions AS SELECT * FROM functions WHERE 0")
            conn.execute("DELETE FROM _backup_functions")
            conn.execute("INSERT INTO _backup_functions SELECT * FROM functions")
            conn.execute("CREATE TABLE IF NOT EXISTS _backup_calls AS SELECT * FROM calls WHERE 0")
            conn.execute("DELETE FROM _backup_calls")
            conn.execute("INSERT INTO _backup_calls SELECT * FROM calls")
            conn.execute("CREATE TABLE IF NOT EXISTS _backup_code_references AS SELECT * FROM code_references WHERE 0")
            conn.execute("DELETE FROM _backup_code_references")
            conn.execute("INSERT INTO _backup_code_references SELECT * FROM code_references")
            conn.commit()
            backup_success = True
            logger.debug("旧数据已备份到临时表")
        except Exception as e:
            conn.rollback()
            # BUG-UE-003修复：备份失败时中止同步
            logger.error(f"备份数据失败，中止同步: {e}")
            raise RuntimeError(f"全量同步备份数据失败: {e}")

        # 清空现有数据
        try:
            conn.execute("DELETE FROM calls")
            conn.execute("DELETE FROM code_references")
            conn.execute("DELETE FROM functions")
            conn.execute("DELETE FROM types")
            conn.execute("DELETE FROM files")
            conn.commit()
        except Exception as e:
            conn.rollback()
            # BUG-UE-004修复：清空失败时抛出异常
            logger.error(f"全量同步清空数据失败: {e}")
            raise RuntimeError(f"全量同步清空数据失败: {e}")

        extensions_map = FileWatcher.get_language_extensions()
        extensions = set(extensions_map.keys())

        # 收集所有文件
        # BUG-UPDATE-002修复：设置followlinks=False并添加符号链接循环检测
        all_files = []
        visited_real_paths = set()  # 用于检测符号链接循环
        
        for root_dir, dir_names, file_names in os.walk(self.project_path, followlinks=False):
            # BUG-UPDATE-002修复：检测符号链接循环
            real_root = os.path.realpath(root_dir)
            if real_root in visited_real_paths:
                logger.warning(f"检测到符号链接循环，跳过目录: {root_dir} -> {real_root}")
                dir_names[:] = []  # 不再遍历子目录
                continue
            visited_real_paths.add(real_root)
            
            dir_names[:] = [
                d for d in dir_names
                if d not in {"__pycache__", "node_modules", ".git", "venv",
                             ".venv", "build", "dist", ".idea", ".vscode",
                             "target", ".gradle", "vendor", "Pods"}
            ]
            for file_name in file_names:
                ext = os.path.splitext(file_name)[1].lower()
                if ext in extensions:
                    all_files.append(os.path.join(root_dir, file_name))

        total_files = len(all_files)
        updated_files = 0

        # 第一阶段：提取所有实体（不建立跨文件引用）
        logger.info(f"全量同步第一阶段: 提取{total_files}个文件的实体...")
        parse_results = {}  # file_path -> (file_id, parse_result)
        for file_path in all_files:
            try:
                file_id, parse_result = self._update_single_file_phase1(file_path)
                if file_id:
                    parse_results[file_path] = (file_id, parse_result)
                    updated_files += 1
            except Exception as exception:
                logger.error(f"全量同步失败 {file_path}: {exception}")

        # 第二阶段：建立跨文件引用关系
        logger.info(f"全量同步第二阶段: 建立{updated_files}个文件的引用关系...")
        for file_path, (file_id, parse_result) in parse_results.items():
            try:
                if parse_result and parse_result.references:
                    self._store_references_only(file_id, parse_result)
            except Exception as exception:
                logger.error(f"引用关系建立失败 {file_path}: {exception}")

        # BUG-UE-004修复：同步成功后删除备份表
        try:
            for table in ["_backup_files", "_backup_types", "_backup_functions",
                          "_backup_calls", "_backup_code_references"]:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
            logger.debug("备份表已清理")
        except Exception as e:
            logger.warning(f"清理备份表失败: {e}")

        self.stats["total_updates"] += 1
        self.stats["last_update_time"] = datetime.now().isoformat()
        logger.info(f"全量同步完成: 共{total_files}个文件, 成功{updated_files}个")
        return {"total": total_files, "updated": updated_files}

    def _update_single_file_phase1(self, file_path: str, event_type: str = "created"):
        """全量同步第一阶段：只提取实体，不建立跨文件引用"""
        file_path = os.path.abspath(file_path)

        language = FileWatcher.detect_language(file_path)
        if not language:
            return None, None

        parse_result = None
        try:
            parser = self.parser_registry.get_parser(language)
            if parser:
                parse_result = parser.parse_file(file_path)
        except Exception as e:
            logger.warning(f"解析文件失败 {file_path}: {e}")
            parse_result = None

        file_hash = self.database.compute_file_hash(file_path)

        try:
            file_id = self.database.upsert_file(file_path, language, file_hash)

            if parse_result:
                # 只存储types和functions（不存储references）
                type_id_map = {}
                if parse_result.types:
                    type_ids = self.database.insert_types(file_id, [
                        {"name": t.name, "kind": t.kind, "flags": t.flags,
                         "start_line": t.start_line, "end_line": t.end_line}
                        for t in parse_result.types
                    ])
                    for type_info, type_id in zip(parse_result.types, type_ids):
                        type_id_map[type_info.name] = type_id

                entity_id_map = dict(type_id_map)
                if parse_result.functions:
                    func_ids = self.database.insert_functions(file_id, [
                        {"name": f.name, "type_name": f.type_name,
                         "start_line": f.start_line, "end_line": f.end_line}
                        for f in parse_result.functions
                    ], type_id_map)
                    for func_info, func_id in zip(parse_result.functions, func_ids):
                        composite_key = f"{func_info.name}@{func_info.type_name}"
                        entity_id_map[composite_key] = func_id
                        if func_info.name not in entity_id_map:
                            entity_id_map[func_info.name] = func_id

                # 存储calls（文件内调用关系）
                if parse_result.calls:
                    caller_map = {}
                    callee_map = {}
                    for c in parse_result.calls:
                        caller_map[c.caller] = entity_id_map.get(c.caller)
                        callee_map[c.callee] = entity_id_map.get(c.callee)
                    self.database.insert_calls(
                        [{"caller": c.caller, "callee": c.callee}
                         for c in parse_result.calls],
                        caller_map, callee_map
                    )

            self.database.commit()
            return file_id, parse_result
        except Exception:
            self.database.rollback()
            raise

    def _store_references_only(self, file_id: int, parse_result):
        """全量同步第二阶段：只建立引用关系"""
        conn = self.database._get_connection()
        entity_id_map = {}

        # 构建当前文件的entity_id_map
        for row in conn.execute(
            "SELECT id, name FROM types WHERE file_id = ?", (file_id,)
        ).fetchall():
            entity_id_map[row["name"]] = row["id"]
        for row in conn.execute(
            "SELECT f.id, f.name, t.name as type_name FROM functions f "
            "LEFT JOIN types t ON f.type_id = t.id WHERE f.file_id = ?", (file_id,)
        ).fetchall():
            # BUG-REF-01修复：LEFT JOIN返回None时用空字符串替代，与第一阶段复合key一致
            type_name = row['type_name'] or ""
            composite_key = f"{row['name']}@{type_name}"
            entity_id_map[composite_key] = row["id"]
            if row["name"] not in entity_id_map:
                entity_id_map[row["name"]] = row["id"]

        if parse_result.references:
            self.database.insert_references(
                [{"from_entity": r.from_entity, "to_entity": r.to_entity, "kind": r.kind}
                 for r in parse_result.references],
                entity_id_map,
                current_file_id=file_id
            )
            try:
                self.database.commit()
            except Exception:
                self.database.rollback()
                raise

    def start(self):
        """启动增量更新引擎"""
        self._running_event.set()  # BUG-UPDATE-010/011修复: 使用Event.set()
        self.file_watcher.start()
        logger.info(f"文件监控已启动: {self.project_path}")

    def start_async_loop(self):
        """启动异步事件处理循环"""
        self._running_event.set()  # BUG-UPDATE-010/011修复: 使用Event.set()
        return self._process_events_loop()

    def stop(self):
        """停止增量更新引擎"""
        self._running_event.clear()  # BUG-UPDATE-010/011修复: 使用Event.clear()
        self.file_watcher.stop()
        logger.info("文件监控已停止")

    async def flush(self):
        """刷新待处理事件"""
        # BUG-FLUSH-01修复：先获取锁取出batch，释放锁后再await
        batch = None
        with self._lock:
            if self._pending_events:
                batch = dict(self._pending_events)
                self._pending_events.clear()
        if batch:
            await asyncio.get_running_loop().run_in_executor(
                None, self._process_batch_sync, batch
            )
