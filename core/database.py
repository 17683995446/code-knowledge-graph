"""
Knowledge Database - 知识图谱数据库管理
基于SQLite的代码知识图谱存储，支持所有编程语言
修复: 线程安全、事务原子性、INSERT OR IGNORE
"""

import sqlite3
import hashlib
import os
import threading
import logging
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    """文件记录数据类"""
    file_id: int
    file_path: str
    language: str
    file_hash: bytes
    modified_time: int


class KnowledgeDatabase:
    """
    代码知识图谱数据库
    线程安全：每个线程使用独立连接，通过 thread-local 实现
    事务原子性：文件更新在单个事务中完成
    BUG-DB-002修复：维护所有线程连接的列表，在close时全部关闭
    """

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY,
        path TEXT UNIQUE NOT NULL,
        language TEXT NOT NULL,
        hash BLOB NOT NULL,
        modified INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS types (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        file_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        flags INTEGER NOT NULL DEFAULT 0,
        start_line INTEGER,
        end_line INTEGER,
        UNIQUE(name, file_id)
    );

    CREATE TABLE IF NOT EXISTS functions (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        type_id INTEGER NOT NULL,
        file_id INTEGER NOT NULL,
        start_line INTEGER,
        end_line INTEGER
    );

    CREATE TABLE IF NOT EXISTS calls (
        caller_id INTEGER NOT NULL,
        callee_id INTEGER NOT NULL,
        PRIMARY KEY (caller_id, callee_id)
    );

    CREATE TABLE IF NOT EXISTS code_references (
        from_id INTEGER NOT NULL,
        to_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        PRIMARY KEY (from_id, to_id, kind)
    );

    CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
    CREATE INDEX IF NOT EXISTS idx_files_language ON files(language);
    CREATE INDEX IF NOT EXISTS idx_types_file ON types(file_id);
    CREATE INDEX IF NOT EXISTS idx_functions_file ON functions(file_id);
    CREATE INDEX IF NOT EXISTS idx_functions_type ON functions(type_id);
    CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_id);
    CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_id);
    CREATE INDEX IF NOT EXISTS idx_refs_from ON code_references(from_id);
    CREATE INDEX IF NOT EXISTS idx_refs_to ON code_references(to_id);
    """

    def __init__(self, database_path: str = "code_knowledge.db"):
        self.database_path = database_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._write_lock = threading.RLock()  # BUG-DB-CONC-001修复: 使用RLock避免死锁
        # BUG-DB-002修复：维护所有线程连接的列表
        self._all_connections: List[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()
        
        # BUG-DB-RECV-001修复：检测数据库完整性，损坏时自动备份并重建
        self._check_and_recover_database()
        
        # BUG-DB-009修复：建表失败时进行清理
        conn = None
        try:
            conn = self._get_connection()
            conn.executescript(self.SCHEMA_SQL)
            conn.commit()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            # BUG-DB-009修复：建表失败后清理连接
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass
            # 从连接列表中移除
            with self._connections_lock:
                if conn in self._all_connections:
                    self._all_connections.remove(conn)
            if hasattr(self._local, 'connection'):
                self._local.connection = None
            raise

    def _check_and_recover_database(self):
        """
        BUG-DB-RECV-001修复：检测数据库完整性，损坏时自动备份并重建
        """
        if not os.path.exists(self.database_path):
            # 数据库不存在，无需检查
            return
        
        # 检查数据库完整性
        try:
            conn = sqlite3.connect(self.database_path, timeout=5.0)
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            
            if result and result[0] == "ok":
                # 数据库完整，无需恢复
                return
            
            # 数据库损坏，进行恢复
            logger.warning(f"数据库损坏，正在备份并重建: {self.database_path}")
            self._backup_and_rebuild_database()
            
        except sqlite3.DatabaseError as e:
            logger.warning(f"数据库损坏或无法访问: {e}，正在备份并重建")
            self._backup_and_rebuild_database()
        except Exception as e:
            logger.error(f"数据库完整性检查失败: {e}")

    def _backup_and_rebuild_database(self):
        """
        BUG-DB-RECV-001修复：备份损坏的数据库并重建
        BUG-DB-RECV-002修复：尝试从损坏数据库恢复数据，避免完全丢失
        """
        try:
            # 生成备份文件名（带时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.database_path}.corrupted_{timestamp}"
            recovery_db_path = f"{self.database_path}.recovery_{timestamp}.db"
            
            # BUG-DB-RECV-002修复：先尝试从损坏数据库恢复数据
            recovery_success = False
            if os.path.exists(self.database_path):
                try:
                    # 尝试使用.dump命令导出数据
                    conn = sqlite3.connect(self.database_path, timeout=5.0)
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    
                    # 创建恢复数据库
                    recovery_conn = sqlite3.connect(recovery_db_path)
                    
                    # 尝试复制数据
                    for line in conn.iterdump():
                        try:
                            recovery_conn.execute(line)
                        except sqlite3.Error:
                            pass  # 忽略无法恢复的数据
                    
                    recovery_conn.commit()
                    recovery_conn.close()
                    conn.close()
                    
                    logger.info(f"数据已恢复到: {recovery_db_path}")
                    recovery_success = True
                except Exception as e:
                    logger.warning(f"数据恢复尝试失败: {e}")
            
            # 备份损坏的数据库文件
            if os.path.exists(self.database_path):
                shutil.move(self.database_path, backup_path)
                logger.info(f"损坏的数据库已备份到: {backup_path}")
            
            # BUG-DB-RECV-002修复：如果恢复成功，使用恢复的数据库
            if recovery_success and os.path.exists(recovery_db_path):
                shutil.move(recovery_db_path, self.database_path)
                logger.info(f"使用恢复的数据库替换损坏的数据库")
            else:
                # 删除可能的WAL和SHM文件
                for ext in ["-wal", "-shm"]:
                    wal_path = f"{self.database_path}{ext}"
                    if os.path.exists(wal_path):
                        os.remove(wal_path)
                
                # 清理恢复失败的临时文件
                if os.path.exists(recovery_db_path):
                    os.remove(recovery_db_path)
                    
            logger.info("数据库已重建")
            
        except Exception as e:
            logger.error(f"数据库备份重建失败: {e}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """
        获取当前线程的数据库连接（线程安全）
        BUG-DB-002修复：将新连接添加到全局列表
        """
        conn = getattr(self._local, 'connection', None)
        if conn is None:
            conn = sqlite3.connect(self.database_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.connection = conn
            # BUG-DB-002修复：将连接添加到全局列表
            with self._connections_lock:
                self._all_connections.append(conn)
        return conn

    @property
    def connection(self) -> sqlite3.Connection:
        """兼容旧代码的连接属性"""
        return self._get_connection()

    def compute_file_hash(self, file_path: str) -> bytes:
        """计算文件的SHA256哈希值"""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(8192), b""):
                hasher.update(chunk)
        return hasher.digest()

    def upsert_file(self, file_path: str, language: str, file_hash: bytes) -> int:
        """插入或更新文件记录，返回文件ID（不commit，由调用者控制事务）
        BUG-DB-003修复: 使用写入锁保护并发写入
        """
        try:
            modified_time = int(os.path.getmtime(file_path))
        except (OSError, FileNotFoundError):
            modified_time = 0
        conn = self._get_connection()
        with self._write_lock:  # BUG-DB-003修复: 加写入锁
            # 先尝试查询已有记录
            existing = conn.execute(
                "SELECT id FROM files WHERE path = ?", (file_path,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE files SET language=?, hash=?, modified=? WHERE path=?",
                    (language, file_hash, modified_time, file_path)
                )
                return existing["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO files (path, language, hash, modified) VALUES (?, ?, ?, ?)",
                    (file_path, language, file_hash, modified_time)
                )
                return cursor.lastrowid

    def get_file_by_path(self, file_path: str) -> Optional[FileRecord]:
        """根据路径查询文件记录"""
        row = self._get_connection().execute(
            "SELECT id, path, language, hash, modified FROM files WHERE path = ?",
            (file_path,)
        ).fetchone()
        if row:
            return FileRecord(
                file_id=row["id"], file_path=row["path"],
                language=row["language"], file_hash=row["hash"],
                modified_time=row["modified"]
            )
        return None

    def delete_file_cascade(self, file_id: int):
        """级联删除文件及其所有关联数据（不commit，由调用者控制事务）
        BUG-DB-007修复: 添加空列表检查，避免SQL语法错误
        BUG-DB-011修复: 整个操作包装在事务中
        BUG-DB-003修复: 使用写入锁保护并发写入
        """
        conn = self._get_connection()
        with self._write_lock:  # BUG-DB-003修复: 加写入锁
            cursor = conn.cursor()
            type_ids = cursor.execute(
                "SELECT id FROM types WHERE file_id = ?", (file_id,)
            ).fetchall()
            type_id_list = [t["id"] for t in type_ids]

            function_ids = cursor.execute(
                "SELECT id FROM functions WHERE file_id = ?", (file_id,)
            ).fetchall()
            function_id_list = [f["id"] for f in function_ids]

            all_entity_ids = type_id_list + function_id_list
            # BUG-DB-007修复: 添加空列表检查，避免SQL语法错误
            if all_entity_ids:
                placeholders = ",".join("?" * len(all_entity_ids))
                cursor.execute(
                    f"DELETE FROM calls WHERE caller_id IN ({placeholders}) OR callee_id IN ({placeholders})",
                    all_entity_ids * 2
                )
                cursor.execute(
                    f"DELETE FROM code_references WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})",
                    all_entity_ids * 2
                )

            cursor.execute("DELETE FROM functions WHERE file_id = ?", (file_id,))
            cursor.execute("DELETE FROM types WHERE file_id = ?", (file_id,))
            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
            # 注意: 不在此处commit，由调用者控制事务边界

    def insert_types(self, file_id: int, types_data: List[Dict[str, Any]]) -> List[int]:
        """批量插入类型实体（使用INSERT OR IGNORE避免重复，不commit）
        BUG-DB-003修复: 使用写入锁保护并发写入
        """
        conn = self._get_connection()
        inserted_ids = []
        with self._write_lock:  # BUG-DB-003修复: 加写入锁
            for type_info in types_data:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO types (name, file_id, kind, flags, start_line, end_line) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        type_info["name"], file_id, type_info["kind"],
                        type_info.get("flags", 0),
                        type_info.get("start_line"), type_info.get("end_line")
                    )
                )
                if cursor.lastrowid:
                    inserted_ids.append(cursor.lastrowid)
                else:
                    # INSERT OR IGNORE被忽略，查询已存在记录的ID
                    existing = conn.execute(
                        "SELECT id FROM types WHERE name=? AND file_id=?",
                        (type_info["name"], file_id)
                    ).fetchone()
                    inserted_ids.append(existing["id"] if existing else 0)
        return inserted_ids

    def insert_functions(self, file_id: int, functions_data: List[Dict[str, Any]],
                         type_id_map: Dict[str, int]) -> List[int]:
        """批量插入函数实体（不commit）
        BUG-DB-012修复: 添加type_id有效性检查，type_id为0时跳过插入
        BUG-DB-003修复: 使用写入锁保护并发写入
        """
        conn = self._get_connection()
        inserted_ids = []
        with self._write_lock:  # BUG-DB-003修复: 加写入锁
            for func_info in functions_data:
                type_name = func_info.get("type_name", "") or "__module__"
                type_id = type_id_map.get(type_name)
                if type_id is None:
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO types (name, file_id, kind, flags) VALUES (?, ?, 'module', 0)",
                        (type_name, file_id)
                    )
                    type_id = cursor.lastrowid
                    if type_id:
                        type_id_map[type_name] = type_id
                    else:
                        # 类型已存在，查询获取ID
                        existing = conn.execute(
                            "SELECT id FROM types WHERE name=? AND file_id=?",
                            (type_name, file_id)
                        ).fetchone()
                        type_id = existing["id"] if existing else 0
                        type_id_map[type_name] = type_id

                # BUG-DB-012修复: type_id为0时跳过插入，避免无效外键
                if type_id and type_id > 0:
                    cursor = conn.execute(
                        "INSERT INTO functions (name, type_id, file_id, start_line, end_line) VALUES (?, ?, ?, ?, ?)",
                        (
                            func_info["name"], type_id, file_id,
                            func_info.get("start_line"), func_info.get("end_line")
                        )
                    )
                    inserted_ids.append(cursor.lastrowid)
                else:
                    logger.warning(f"跳过函数插入，无效的type_id: {func_info['name']}, type_id={type_id}")
                    inserted_ids.append(0)  # 返回0表示未插入
        return inserted_ids

    def insert_calls(self, calls_data: List[Dict[str, Any]],
                     caller_id_map: Dict[str, int], callee_id_map: Dict[str, int]):
        """批量插入调用关系（不commit）
        BUG-DB-003修复: 使用写入锁保护并发写入
        """
        conn = self._get_connection()
        with self._write_lock:  # BUG-DB-003修复: 加写入锁
            for call_info in calls_data:
                caller_id = caller_id_map.get(call_info["caller"])
                callee_id = callee_id_map.get(call_info["callee"])
                if caller_id and callee_id and caller_id != callee_id:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO calls (caller_id, callee_id) VALUES (?, ?)",
                            (caller_id, callee_id)
                        )
                    except sqlite3.IntegrityError:
                        pass

    def insert_references(self, refs_data: List[Dict[str, Any]],
                          entity_id_map: Dict[str, int],
                          current_file_id: int = 0):
        """批量插入引用关系，支持跨文件实体查找（不commit）
        BUG-REF-03修复：同时查types和functions表
        BUG-REF-04修复：__imports__引用自动关联当前文件所有实体
        BUG-DB-003修复: 使用写入锁保护并发写入
        """
        conn = self._get_connection()
        with self._write_lock:  # BUG-DB-003修复: 加写入锁
            for ref_info in refs_data:
                from_entity = ref_info["from_entity"]
                to_entity = ref_info["to_entity"]
                from_id = entity_id_map.get(from_entity)
                to_id = entity_id_map.get(to_entity)

                # __imports__ 引用：表示当前文件导入了 to_entity
                # 只将当前文件的types（类/接口）作为 from_id，不关联functions
                if from_entity == "__imports__" and current_file_id:
                    to_id = self._find_entity_id(conn, to_entity)
                    if to_id:
                        for row in conn.execute(
                            "SELECT id FROM types WHERE file_id = ? AND kind != 'module'",
                            (current_file_id,)
                        ).fetchall():
                            fid = row["id"]
                            if fid != to_id:
                                try:
                                    conn.execute(
                                        "INSERT OR IGNORE INTO code_references (from_id, to_id, kind) VALUES (?, ?, ?)",
                                        (fid, to_id, ref_info["kind"])
                                    )
                                except sqlite3.IntegrityError:
                                    pass
                    continue

                # __module__ 引用：类似处理，只关联types
                if from_entity == "__module__" and current_file_id:
                    to_id = self._find_entity_id(conn, to_entity)
                    if to_id:
                        for row in conn.execute(
                            "SELECT id FROM types WHERE file_id = ? AND kind != 'module'",
                            (current_file_id,)
                        ).fetchall():
                            fid = row["id"]
                            if fid != to_id:
                                try:
                                    conn.execute(
                                        "INSERT OR IGNORE INTO code_references (from_id, to_id, kind) VALUES (?, ?, ?)",
                                        (fid, to_id, ref_info["kind"])
                                    )
                                except sqlite3.IntegrityError:
                                    pass
                    continue

                # 常规引用：跨文件查找
                if from_id and not to_id:
                    to_id = self._find_entity_id(conn, to_entity)

                if to_id and not from_id:
                    from_id = self._find_entity_id(conn, from_entity)

                if from_id and to_id and from_id != to_id:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO code_references (from_id, to_id, kind) VALUES (?, ?, ?)",
                            (from_id, to_id, ref_info["kind"])
                        )
                    except sqlite3.IntegrityError:
                        pass

    def _find_entity_id(self, conn, name: str) -> Optional[int]:
        """在types和functions表中查找实体ID"""
        if not name or name == "__module__":
            return None
        # 先查types表
        row = conn.execute(
            "SELECT id FROM types WHERE name = ? LIMIT 1",
            (name,)
        ).fetchone()
        if row:
            return row["id"]
        # 再查functions表
        row = conn.execute(
            "SELECT id FROM functions WHERE name = ? LIMIT 1",
            (name,)
        ).fetchone()
        if row:
            return row["id"]
        return None

    def commit(self):
        """提交当前线程的事务"""
        self._get_connection().commit()

    def rollback(self):
        """回滚当前线程的事务"""
        self._get_connection().rollback()

    def get_all_files(self) -> List[FileRecord]:
        """获取所有文件记录"""
        rows = self._get_connection().execute(
            "SELECT id, path, language, hash, modified FROM files ORDER BY path"
        ).fetchall()
        return [
            FileRecord(
                file_id=r["id"], file_path=r["path"],
                language=r["language"], file_hash=r["hash"],
                modified_time=r["modified"]
            ) for r in rows
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """获取知识图谱统计信息"""
        conn = self._get_connection()
        stats = {}
        stats["total_files"] = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        stats["total_types"] = conn.execute("SELECT COUNT(*) FROM types").fetchone()[0]
        stats["total_functions"] = conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]
        stats["total_calls"] = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        stats["total_references"] = conn.execute("SELECT COUNT(*) FROM code_references").fetchone()[0]

        language_stats = conn.execute(
            "SELECT language, COUNT(*) as count FROM files GROUP BY language ORDER BY count DESC"
        ).fetchall()
        stats["languages"] = {lang["language"]: lang["count"] for lang in language_stats}

        kind_stats = conn.execute(
            "SELECT kind, COUNT(*) as count FROM types GROUP BY kind ORDER BY count DESC"
        ).fetchall()
        stats["type_kinds"] = {k["kind"]: k["count"] for k in kind_stats}

        ref_kind_stats = conn.execute(
            "SELECT kind, COUNT(*) as count FROM code_references GROUP BY kind ORDER BY count DESC"
        ).fetchall()
        stats["reference_kinds"] = {k["kind"]: k["count"] for k in ref_kind_stats}

        return stats

    def get_graph_data(self, limit: int = 5000) -> Dict[str, Any]:
        """获取完整的图谱数据用于可视化
        BUG-DB-MEM-001修复: 添加limit参数限制返回节点和边的数量
        """
        conn = self._get_connection()
        nodes = []
        edges = []

        # 构建有效实体ID集合，用于过滤悬空引用
        valid_type_ids = set()
        valid_func_ids = set()

        # BUG-DB-MEM-001修复: 添加LIMIT限制查询结果数量
        type_rows = conn.execute("""
            SELECT t.id, t.name, t.kind, t.flags, t.file_id, f.path as file_path, f.language
            FROM types t JOIN files f ON t.file_id = f.id
            LIMIT ?
        """, (limit,)).fetchall()
        for row in type_rows:
            valid_type_ids.add(row["id"])
            nodes.append({
                "id": f"type_{row['id']}",
                "label": row["name"],
                "kind": row["kind"],
                "language": row["language"],
                "file_path": row["file_path"],
                "group": "type"
            })

        func_rows = conn.execute("""
            SELECT fn.id, fn.name, fn.file_id, f.path as file_path, f.language
            FROM functions fn JOIN files f ON fn.file_id = f.id
            LIMIT ?
        """, (limit,)).fetchall()
        for row in func_rows:
            valid_func_ids.add(row["id"])
            nodes.append({
                "id": f"func_{row['id']}",
                "label": row["name"],
                "kind": "function",
                "language": row["language"],
                "file_path": row["file_path"],
                "group": "function"
            })

        # 调用关系 - 只保留两端都存在的边
        # BUG-DB-MEM-001修复: 添加LIMIT限制边数量
        call_rows = conn.execute("SELECT caller_id, callee_id FROM calls LIMIT ?", (limit,)).fetchall()
        for row in call_rows:
            if row["caller_id"] in valid_func_ids and row["callee_id"] in valid_func_ids:
                edges.append({
                    "source": f"func_{row['caller_id']}",
                    "target": f"func_{row['callee_id']}",
                    "kind": "call"
                })

        # 引用关系 - 只保留两端都存在的边，正确判断类型
        # BUG-DB-MEM-001修复: 添加LIMIT限制边数量
        ref_rows = conn.execute("""
            SELECT from_id, to_id, kind FROM code_references
            LIMIT ?
        """, (limit,)).fetchall()
        for row in ref_rows:
            from_id = row["from_id"]
            to_id = row["to_id"]
            prefix_from = "type" if from_id in valid_type_ids else ("func" if from_id in valid_func_ids else None)
            prefix_to = "type" if to_id in valid_type_ids else ("func" if to_id in valid_func_ids else None)
            if prefix_from and prefix_to:
                edges.append({
                    "source": f"{prefix_from}_{from_id}",
                    "target": f"{prefix_to}_{to_id}",
                    "kind": row["kind"]
                })

        return {"nodes": nodes, "edges": edges}

    def get_file_details(self, file_path: str) -> Dict[str, Any]:
        """获取单个文件的详细知识图谱数据"""
        conn = self._get_connection()
        file_record = self.get_file_by_path(file_path)
        if not file_record:
            return {}

        types = conn.execute(
            "SELECT * FROM types WHERE file_id = ?", (file_record.file_id,)
        ).fetchall()

        functions = conn.execute(
            "SELECT * FROM functions WHERE file_id = ?", (file_record.file_id,)
        ).fetchall()

        type_ids = [t["id"] for t in types]
        func_ids = [f["id"] for f in functions]
        all_ids = type_ids + func_ids

        calls = []
        references = []
        if all_ids:
            placeholders = ",".join("?" * len(all_ids))
            call_rows = conn.execute(
                f"SELECT caller_id, callee_id FROM calls WHERE caller_id IN ({placeholders}) OR callee_id IN ({placeholders})",
                all_ids * 2
            ).fetchall()
            calls = [dict(row) for row in call_rows]

            ref_rows = conn.execute(
                f"SELECT from_id, to_id, kind FROM code_references WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})",
                all_ids * 2
            ).fetchall()
            references = [dict(row) for row in ref_rows]

        return {
            "file": {"path": file_record.file_path, "language": file_record.language},
            "types": [dict(t) for t in types],
            "functions": [dict(f) for f in functions],
            "calls": calls,
            "references": references
        }

    def get_dependency_graph(self, limit: int = 10000) -> Dict[str, Any]:
        """
        获取文件级别的依赖图
        BUG-DB-MEM-003修复: 添加limit参数限制返回的依赖数量，防止内存溢出
        """
        # 限制最大值为50000，防止内存溢出
        if limit > 50000:
            limit = 50000
            
        conn = self._get_connection()
        # BUG-DB-MEM-003修复: 添加LIMIT限制查询结果数量
        file_deps = conn.execute("""
            SELECT f1.path as from_file, f2.path as to_file, r.kind
            FROM code_references r
            JOIN types t1 ON r.from_id = t1.id JOIN files f1 ON t1.file_id = f1.id
            JOIN types t2 ON r.to_id = t2.id JOIN files f2 ON t2.file_id = f2.id
            WHERE f1.path != f2.path
            UNION ALL
            SELECT f1.path as from_file, f2.path as to_file, r.kind
            FROM code_references r
            JOIN functions fn1 ON r.from_id = fn1.id JOIN files f1 ON fn1.file_id = f1.id
            JOIN functions fn2 ON r.to_id = fn2.id JOIN files f2 ON fn2.file_id = f2.id
            WHERE f1.path != f2.path
            LIMIT ?
        """, (limit,)).fetchall()

        nodes = set()
        edges = []
        for row in file_deps:
            nodes.add(row["from_file"])
            nodes.add(row["to_file"])
            edges.append({
                "source": row["from_file"],
                "target": row["to_file"],
                "kind": row["kind"]
            })

        return {
            "nodes": [{"id": n, "label": os.path.basename(n)} for n in nodes],
            "edges": edges
        }

    def close(self):
        """
        关闭所有线程的数据库连接
        BUG-DB-002修复：维护所有线程连接的列表，在close时全部关闭
        BUG-DB-OTHER-001修复：关闭前执行WAL checkpoint确保数据持久化
        """
        # BUG-DB-OTHER-001修复：关闭前执行WAL checkpoint
        conn = getattr(self._local, 'connection', None)
        if conn:
            try:
                # 执行WAL checkpoint，将WAL文件内容合并到主数据库
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.commit()
                logger.debug("WAL checkpoint已完成")
            except Exception as e:
                logger.warning(f"执行WAL checkpoint失败: {e}")
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"关闭数据库连接失败: {e}")
            self._local.connection = None
        
        # BUG-DB-002修复：关闭所有线程的连接
        with self._connections_lock:
            for c in self._all_connections:
                if c is not conn:  # 避免重复关闭当前线程的连接
                    try:
                        # BUG-DB-OTHER-001修复：对每个连接执行checkpoint
                        try:
                            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                            c.commit()
                        except Exception:
                            pass
                        c.close()
                    except Exception as e:
                        logger.warning(f"关闭其他线程数据库连接失败: {e}")
            self._all_connections.clear()
