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
- BUG-UE-RECV-004: 检查点机制，支持全量同步中断后恢复
"""

import os
import asyncio
import logging
import threading
import queue
import json
from queue import Queue, Full
from typing import Dict, Set, Optional, Callable, Any
from datetime import datetime

from core.database import KnowledgeDatabase
from core.file_watcher import FileWatcher
from parsers.parser_registry import ParserRegistry

logger = logging.getLogger(__name__)


class UpdateEngine:
    """
    增量更新引擎
    核心职责：接收文件变更 → 防抖合并 → 增量更新数据库
    BUG-UE-RECV-004修复：支持检查点机制，全量同步中断后可恢复
    """

    # BUG-UE-RECV-004: 检查点相关常量
    CHECKPOINT_TABLE = "_sync_checkpoint"
    CHECKPOINT_FILE = ".code_kg_checkpoint.json"

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
        # BUG-STATE-RACE-01修复: 添加状态锁保护启动/停止操作
        self._state_lock = threading.Lock()
        # BUG-UPDATE-010/011修复: 使用threading.Event替代bool标志，确保原子操作
        self._running_event = threading.Event()
        self._running_event.set()  # 初始状态为运行
        self._loop = None  # 保存asyncio事件循环引用

        # BUG-UE-RECV-004: 检查点相关属性
        self._checkpoint_path = os.path.join(self.project_path, self.CHECKPOINT_FILE)
        self._sync_in_progress = False
        self._sync_progress: Dict[str, Any] = {}

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
        """文件事件回调（同步，由watchdog线程调用）
        BUG-EVENT-STORM-01修复：使用put_nowait()并捕获queue.Full异常
        """
        try:
            self._event_queue.put_nowait((file_path, event_type))
        except queue.Full:
            logger.warning(f"事件队列已满，丢弃事件: {file_path}")

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
            # BUG-AUDIT-029修复：追加错误而非覆盖，保留最近100条
            if "errors" not in self.stats:
                self.stats["errors"] = []
            self.stats["errors"].extend(errors)
            self.stats["errors"] = self.stats["errors"][-100:]

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
        BUG-FS-LOCK-01/PERMISSION-01修复：添加PermissionError、IOError、OSError异常处理
        BUG-DB-TRANSACTION-01修复：使用SAVEPOINT实现嵌套事务，确保删除+插入原子性
        """
        file_path = os.path.abspath(file_path)

        if event_type == "deleted":
            # BUG-SINGLE-01修复：添加异常保护，确保删除失败不导致整个批处理中断
            # BUG-AUDIT-005修复：所有异常路径都执行rollback，确保数据库一致性
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

            # BUG-FS-LOCK-01/PERMISSION-01修复：检查文件访问权限
            try:
                if not os.access(file_path, os.R_OK):
                    logger.warning(f"文件无读取权限，跳过: {file_path}")
                    return
            except OSError as e:
                logger.warning(f"无法检查文件权限 {file_path}: {e}")
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
                except PermissionError as e:
                    logger.warning(f"权限不足，无法解析文件 {file_path}: {e}")
                    parse_result = None
                    parse_success = False
                except IOError as e:
                    logger.warning(f"IO错误，无法解析文件 {file_path}: {e}")
                    parse_result = None
                    parse_success = False
                except OSError as e:
                    logger.warning(f"系统错误，无法解析文件 {file_path}: {e}")
                    parse_result = None
                    parse_success = False
                except Exception as e:
                    logger.warning(f"解析文件失败 {file_path}: {e}，保留旧数据")
                    parse_result = None
                    parse_success = False

            # BUG-FS-LOCK-01/PERMISSION-01修复：计算文件哈希时捕获异常
            try:
                file_hash = self.database.compute_file_hash(file_path)
            except PermissionError as e:
                logger.warning(f"权限不足，无法读取文件 {file_path}: {e}")
                return
            except IOError as e:
                logger.warning(f"IO错误，无法读取文件 {file_path}: {e}")
                return
            except OSError as e:
                logger.warning(f"系统错误，无法读取文件 {file_path}: {e}")
                return

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

            # BUG-DB-TRANSACTION-01修复：使用SAVEPOINT确保删除+插入的原子性
            conn = self.database._get_connection()
            try:
                # 创建SAVEPOINT，保护后续操作
                conn.execute("SAVEPOINT file_update")
                
                file_record = self.database.get_file_by_path(file_path)
                if file_record:
                    self.database.delete_file_cascade(file_record.file_id)

                file_id = self.database.upsert_file(file_path, language, file_hash)

                if parse_result:
                    self._store_parse_result(file_id, parse_result)

                # 释放SAVEPOINT（确认操作）
                conn.execute("RELEASE SAVEPOINT file_update")
                self.database.commit()
            except Exception as e:
                # BUG-DB-TRANSACTION-01修复：回滚到SAVEPOINT，恢复旧数据
                try:
                    conn.execute("ROLLBACK TO SAVEPOINT file_update")
                except Exception:
                    pass
                self.database.rollback()
                logger.error(f"更新文件失败，已回滚: {file_path}: {e}")
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
        BUG-UE-RECV-004修复：支持检查点机制，中断后可恢复
        第一阶段：提取所有文件的实体（types/functions/calls）
        第二阶段：建立跨文件引用关系（references）
        """
        logger.info(f"开始全量同步: {self.project_path}")

        # BUG-UE-RECV-004: 检查是否有待恢复的检查点
        checkpoint = self._load_checkpoint()
        
        # BUG-UE-004修复：先将旧数据备份到临时表，成功后再删除
        conn = self.database._get_connection()
        backup_success = False
        
        # BUG-UE-RECV-004: 只有在没有检查点时才进行备份
        if not checkpoint:
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

        # BUG-UE-RECV-004: 检查是否可以从检查点恢复
        can_resume, files_to_process, already_processed = self._can_resume_from_checkpoint(
            checkpoint, all_files
        )
        
        if can_resume:
            logger.info(f"从检查点恢复同步，跳过{len(already_processed)}个已处理文件")
            # 从检查点恢复时，需要重建parse_results（从数据库读取）
            parse_results = {}
            # 获取已处理文件的file_id
            for file_path in already_processed:
                file_record = self.database.get_file_by_path(file_path)
                if file_record:
                    # 注意：这里无法恢复完整的parse_result，但第一阶段已完成
                    # 只需要继续处理未完成的文件
                    pass
        else:
            files_to_process = all_files

        # 第一阶段：提取所有实体（不建立跨文件引用）
        logger.info(f"全量同步第一阶段: 提取{len(files_to_process)}个文件的实体...")
        # BUG-UE-MEM-001修复：使用列表存储文件ID，避免parse_result占用大量内存
        file_ids_list = []  # 只存储file_id，不存储完整的parse_result
        processed_files = list(already_processed)  # BUG-UE-RECV-004: 从已处理文件开始
        
        for i, file_path in enumerate(files_to_process):
            try:
                file_id, parse_result = self._update_single_file_phase1(file_path)
                if file_id:
                    # BUG-UE-MEM-001修复：只存储file_id，parse_result在第二阶段从数据库读取
                    file_ids_list.append(file_id)
                    updated_files += 1
                    processed_files.append(file_path)  # BUG-UE-RECV-004: 记录已处理文件
                    
                    # BUG-UE-RECV-004: 每100个文件保存一次检查点
                    if (i + 1) % 100 == 0:
                        self._save_checkpoint(processed_files, len(files_to_process), phase=1)
                        
            except Exception as exception:
                logger.error(f"全量同步失败 {file_path}: {exception}")

        # BUG-UE-RECV-004: 第一阶段完成，保存检查点
        self._save_checkpoint(processed_files, len(files_to_process), phase=2)

        # 第二阶段：建立跨文件引用关系
        # BUG-UE-MEM-001修复：分批处理，每批1000个文件，处理完立即释放内存
        logger.info(f"全量同步第二阶段: 建立{updated_files}个文件的引用关系...")
        BATCH_SIZE = 1000  # 每批处理1000个文件
        phase2_errors = 0  # BUG-AUDIT-026修复：记录第二阶段失败数
        for batch_start in range(0, len(file_ids_list), BATCH_SIZE):
            batch_file_ids = file_ids_list[batch_start:batch_start + BATCH_SIZE]
            for file_id in batch_file_ids:
                try:
                    # BUG-UE-MEM-001修复：从数据库读取parse_result，不占用内存
                    parse_result = self._load_parse_result_from_db(file_id)
                    if parse_result and parse_result.references:
                        self._store_references_only(file_id, parse_result)
                except Exception as exception:
                    logger.error(f"引用关系建立失败 file_id={file_id}: {exception}")
                    phase2_errors += 1
            # BUG-UE-MEM-001修复：强制垃圾回收，释放内存
            import gc
            gc.collect()

        # BUG-AUDIT-026修复：如果第二阶段有失败，不清除检查点，允许下次恢复
        if phase2_errors > 0:
            logger.warning(f"第二阶段有 {phase2_errors} 个文件失败，保留检查点以便恢复")
            # 更新检查点状态为需要重新执行第二阶段
            self._save_checkpoint(processed_files, len(files_to_process), phase=2)
        else:
            # BUG-UE-RECV-004: 同步完成，清除检查点
            self._clear_checkpoint()

        # BUG-UE-004修复：同步成功后删除备份表
        try:
            for table in ["_backup_files", "_backup_types", "_backup_functions",
                          "_backup_calls", "_backup_code_references"]:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
            logger.debug("备份表已清理")
        except Exception as e:
            logger.warning(f"清理备份表失败: {e}")

        # BUG-UE-STATS-01修复：使用_stats_lock保护stats的读写操作
        with self._stats_lock:
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

        # BUG-UE-HASH-01修复：添加文件哈希计算异常处理
        try:
            file_hash = self.database.compute_file_hash(file_path)
        except (FileNotFoundError, PermissionError, IOError, OSError) as e:
            logger.warning(f"无法计算文件哈希 {file_path}: {e}")
            return None, None

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
        """启动增量更新引擎
        BUG-STATE-RACE-01修复：添加状态锁保护启动操作
        """
        with self._state_lock:
            self._running_event.set()  # BUG-UPDATE-010/011修复: 使用Event.set()
            self.file_watcher.start()
        logger.info(f"文件监控已启动: {self.project_path}")

    def start_async_loop(self):
        """启动异步事件处理循环
        BUG-STATE-RACE-01修复：添加状态锁保护启动操作
        """
        with self._state_lock:
            self._running_event.set()  # BUG-UPDATE-010/011修复: 使用Event.set()
        return self._process_events_loop()

    def stop(self):
        """停止增量更新引擎
        BUG-STATE-RACE-01修复：添加状态锁保护停止操作
        """
        with self._state_lock:
            self._running_event.clear()  # BUG-UPDATE-010/011修复: 使用Event.clear()
            self.file_watcher.stop()
        logger.info("文件监控已停止")

    async def flush(self):
        """刷新待处理事件
        BUG-AUDIT-018修复：同时处理_event_queue和_pending_events中的事件
        """
        batch = None
        with self._lock:
            # BUG-AUDIT-018修复：先从event_queue中取出所有事件
            while True:
                try:
                    file_path, event_type = self._event_queue.get_nowait()
                    if file_path not in self._pending_events:
                        self._pending_events[file_path] = set()
                    self._pending_events[file_path].add(event_type)
                except Exception:
                    break
            # BUG-FLUSH-01修复：先获取锁取出batch，释放锁后再await
            if self._pending_events:
                batch = dict(self._pending_events)
                self._pending_events.clear()
        if batch:
            await asyncio.get_running_loop().run_in_executor(
                None, self._process_batch_sync, batch
            )

    # ==================== BUG-UE-RECV-004: 检查点机制 ====================

    def _save_checkpoint(self, processed_files: list, total_files: int, phase: int):
        """
        BUG-UE-RECV-004修复：保存同步检查点
        Args:
            processed_files: 已处理的文件列表
            total_files: 总文件数
            phase: 当前阶段（1或2）
        """
        checkpoint_data = {
            "timestamp": datetime.now().isoformat(),
            "project_path": self.project_path,
            "total_files": total_files,
            "processed_count": len(processed_files),
            "processed_files": processed_files,
            "phase": phase
        }
        try:
            # BUG-AUDIT-019修复：使用原子写入模式，先写临时文件再重命名
            tmp_path = self._checkpoint_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False)
            os.replace(tmp_path, self._checkpoint_path)
            logger.debug(f"检查点已保存: {len(processed_files)}/{total_files} 文件, 阶段{phase}")
        except Exception as e:
            logger.warning(f"保存检查点失败: {e}")

    def _load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        BUG-UE-RECV-004修复：加载同步检查点
        Returns:
            检查点数据，如果不存在或无效则返回None
        """
        if not os.path.exists(self._checkpoint_path):
            return None
        try:
            with open(self._checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 验证检查点有效性
            if data.get("project_path") != self.project_path:
                logger.info("检查点项目路径不匹配，忽略")
                return None
            logger.info(f"发现有效检查点: {data.get('processed_count', 0)}/{data.get('total_files', 0)} 文件")
            return data
        except Exception as e:
            logger.warning(f"加载检查点失败: {e}")
            return None

    def _clear_checkpoint(self):
        """BUG-UE-RECV-004修复：清除检查点文件"""
        try:
            if os.path.exists(self._checkpoint_path):
                os.remove(self._checkpoint_path)
                logger.debug("检查点已清除")
        except Exception as e:
            logger.warning(f"清除检查点失败: {e}")

    def _can_resume_from_checkpoint(self, checkpoint: Optional[Dict[str, Any]], 
                                     all_files: list) -> tuple:
        """
        BUG-UE-RECV-004修复：检查是否可以从检查点恢复
        Returns:
            (can_resume, files_to_process, processed_files)
        """
        if not checkpoint:
            return False, all_files, []
        
        processed_files = set(checkpoint.get("processed_files", []))
        # 过滤出未处理的文件
        files_to_process = [f for f in all_files if f not in processed_files]
        
        if files_to_process:
            logger.info(f"从检查点恢复: 跳过{len(processed_files)}个已处理文件，继续处理{len(files_to_process)}个文件")
            return True, files_to_process, list(processed_files)
        
        return False, all_files, []

    def has_pending_checkpoint(self) -> bool:
        """BUG-UE-RECV-004修复：检查是否有待恢复的检查点"""
        return self._load_checkpoint() is not None

    def _load_parse_result_from_db(self, file_id: int):
        """
        BUG-UE-MEM-001修复：从数据库加载解析结果，避免内存占用
        返回一个模拟的ParseResult对象，包含references信息
        """
        from parsers.base_parser import ParseResult, ReferenceInfo
        
        conn = self.database._get_connection()
        
        # 从数据库读取该文件的引用关系
        references = []
        
        # 获取文件路径
        file_row = conn.execute(
            "SELECT path FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        
        if not file_row:
            return None
            
        file_path = file_row["path"]
        
        # 读取types和functions以构建entity_id_map
        type_ids = {}
        for row in conn.execute("SELECT id, name FROM types WHERE file_id = ?", (file_id,)).fetchall():
            type_ids[row["name"]] = row["id"]
        
        func_ids = {}
        for row in conn.execute(
            "SELECT f.id, f.name, t.name as type_name FROM functions f "
            "LEFT JOIN types t ON f.type_id = t.id WHERE f.file_id = ?", (file_id,)
        ).fetchall():
            type_name = row['type_name'] or ""
            composite_key = f"{row['name']}@{type_name}"
            func_ids[composite_key] = row["id"]
            if row["name"] not in func_ids:
                func_ids[row["name"]] = row["id"]
        
        # 构建entity_id_map
        entity_id_map = {**type_ids, **func_ids}
        
        # BUG-AUDIT-024修复：构建反向映射，使用O(1)查找替代O(n*m)遍历
        # 同时确保优先使用简单name而非复合key
        id_to_name = {}
        # 先添加type_ids（优先级低）
        for name, eid in type_ids.items():
            if eid not in id_to_name:
                id_to_name[eid] = name
        # 再添加func_ids的简单name（优先级高）
        for name, eid in func_ids.items():
            if "@" not in name:  # 简单name优先
                id_to_name[eid] = name
        # 最后添加复合key（最低优先级）
        for name, eid in func_ids.items():
            if "@" in name and eid not in id_to_name:
                id_to_name[eid] = name
        
        # 从code_references表读取引用关系
        all_ids = list(type_ids.values()) + list(func_ids.values())
        if all_ids:
            placeholders = ",".join("?" * len(all_ids))
            for row in conn.execute(
                f"SELECT from_id, to_id, kind FROM code_references WHERE from_id IN ({placeholders})",
                tuple(all_ids)
            ).fetchall():
                # BUG-AUDIT-024修复：使用反向映射O(1)查找
                from_name = id_to_name.get(row["from_id"])
                to_name = id_to_name.get(row["to_id"])
                
                if from_name and to_name:
                    references.append(ReferenceInfo(
                        from_entity=from_name,
                        to_entity=to_name,
                        kind=row["kind"]
                    ))
        
        # 创建ParseResult对象（只包含references）
        result = ParseResult()
        result.references = references
        return result
