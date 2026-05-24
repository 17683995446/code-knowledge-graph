"""
第21轮极端复杂场景实战测试
聚焦：模块化规范化 + 复杂场景处理能力验证
"""
import os
import sys
import time
import shutil
import sqlite3
import threading
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import KnowledgeDatabase
from core.update_engine import UpdateEngine
from parsers.parser_registry import ParserRegistry
from parsers.python_parser import PythonParser
from parsers.java_parser import JavaParser

TEST_DIR = None
TEST_DB = None
PASS = 0
FAIL = 0
BUGS = []


def log(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        BUGS.append((name, detail))
        print(f"  ❌ {name} - {detail}")


def setup():
    global TEST_DIR, TEST_DB
    TEST_DIR = tempfile.mkdtemp(prefix="r21_test_")
    TEST_DB = os.path.join(TEST_DIR, "test.db")


def cleanup():
    if TEST_DIR and os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR, ignore_errors=True)


def create_complex_project():
    """创建复杂项目结构：多层嵌套、循环依赖、特殊语法"""
    dirs = [
        "src/core/engine", "src/core/parser", "src/core/analyzer",
        "src/utils", "src/models", "src/services",
        "src/api/v1", "src/api/v2", "src/middleware",
        "src/plugins/alpha", "src/plugins/beta",
        "tests/unit", "tests/e2e",
        "config", "scripts"
    ]
    for d in dirs:
        os.makedirs(os.path.join(TEST_DIR, d), exist_ok=True)

    files = {}

    # 循环依赖场景
    files["src/core/engine/processor.py"] = '''
from src.core.engine.transformer import Transformer
from src.core.engine.validator import Validator

class Processor:
    def __init__(self):
        self.transformer = Transformer()
        self.validator = Validator()

    def process(self, data):
        result = self.transformer.transform(data)
        if self.validator.validate(result):
            return result
        return None

class AdvancedProcessor(Processor):
    def process(self, data):
        result = super().process(data)
        return result
'''

    files["src/core/engine/transformer.py"] = '''
from src.core.engine.processor import Processor

class Transformer:
    def transform(self, data):
        return data

    def reverse(self, data):
        return data[::-1]
'''

    files["src/core/engine/validator.py"] = '''
from src.core.engine.transformer import Transformer

class Validator:
    def __init__(self):
        self.transformer = Transformer()

    def validate(self, data):
        return bool(data)
'''

    # 深层嵌套
    files["src/core/parser/lang/python.py"] = '''
from src.core.parser.base import BaseParser
from src.core.parser.lang.tokens import Tokenizer

class PythonParser(BaseParser):
    def __init__(self):
        self.tokenizer = Tokenizer()

    def parse(self, source):
        tokens = self.tokenizer.tokenize(source)
        return tokens

    def validate(self, source):
        return True

class Python3Parser(PythonParser):
    def parse(self, source):
        result = super().parse(source)
        return result
'''

    files["src/core/parser/base.py"] = '''
class BaseParser:
    def parse(self, source):
        raise NotImplementedError

    def validate(self, source):
        return True
'''

    files["src/core/parser/lang/tokens.py"] = '''
class Tokenizer:
    def tokenize(self, source):
        return source.split()
'''

    # 大量导入
    files["src/services/orchestrator.py"] = '''
from src.core.engine.processor import Processor
from src.core.engine.transformer import Transformer
from src.core.engine.validator import Validator
from src.core.parser.lang.python import PythonParser
from src.core.parser.base import BaseParser
from src.models.user import User
from src.models.order import Order
from src.models.product import Product
from src.utils.logger import Logger
from src.utils.cache import Cache
from src.utils.validator import Validator as V

class Orchestrator:
    def __init__(self):
        self.processor = Processor()
        self.parser = PythonParser()
        self.logger = Logger("Orchestrator")
        self.cache = Cache()

    def run(self, data):
        result = self.processor.process(data)
        self.cache.set("last_result", result)
        return result
'''

    # 模型层
    files["src/models/user.py"] = '''
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

    def validate(self):
        return bool(self.name and self.email)

class AdminUser(User):
    def __init__(self, name, email, role="admin"):
        super().__init__(name, email)
        self.role = role

class GuestUser(User):
    pass
'''

    files["src/models/order.py"] = '''
from src.models.user import User

class Order:
    def __init__(self, user):
        self.user = user

    def validate(self):
        return self.user.validate()

class RefundOrder(Order):
    def process_refund(self):
        pass
'''

    files["src/models/product.py"] = '''
class Product:
    def __init__(self, name, price):
        self.name = name
        self.price = price

class DigitalProduct(Product):
    def download(self):
        pass
'''

    # 工具层
    files["src/utils/logger.py"] = '''
class Logger:
    def __init__(self, name):
        self.name = name
    def info(self, msg):
        pass
    def error(self, msg):
        pass
'''

    files["src/utils/cache.py"] = '''
class Cache:
    def __init__(self):
        self._store = {}
    def get(self, key):
        return self._store.get(key)
    def set(self, key, value):
        self._store[key] = value
'''

    files["src/utils/validator.py"] = '''
class Validator:
    def validate_email(self, email):
        return "@" in email
'''

    # 边界case文件
    files["src/edge/empty.py"] = ""
    files["src/edge/comment_only.py"] = "# just comments\n# more comments\n"
    files["src/edge/unicode_class.py"] = '''
class 用户模型:
    def 获取名称(self):
        return self.name
'''
    files["src/edge/deep_nested.py"] = '''
class A:
    class B:
        class C:
            class D:
                class E:
                    def method(self):
                        pass
'''

    # 嵌套函数调用归属测试
    files["src/edge/nested_calls.py"] = '''
def outer():
    def inner():
        def deepest():
            helper()
        deepest()
    inner()
    helper()

def helper():
    pass
'''

    # Java文件
    files["src/java/Model.java"] = '''
package src.java;
public class Model {
    private String name;
    public Model(String name) { this.name = name; }
    public String getName() { return this.name; }
}
interface Serializable {
    byte[] serialize();
}
class DataModel extends Model implements Serializable {
    public DataModel(String name) { super(name); }
    public byte[] serialize() { return new byte[0]; }
}
'''

    # JavaScript文件
    files["src/js/app.js"] = '''
class App {
    constructor() {
        this.router = new Router();
    }
    init() {
        this.router.register("/", this.handleHome);
    }
    handleHome() { return "Home"; }
}
class Router {
    register(path, handler) { this.routes = {}; this.routes[path] = handler; }
}
class Store extends Router {
    constructor() { super(); this.data = {}; }
    set(key, value) { this.data[key] = value; }
}
'''

    for path, content in files.items():
        full = os.path.join(TEST_DIR, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)

    return files


def test_01_full_sync_complex():
    """测试1: 复杂项目全量同步"""
    print("\n🔍 测试1: 复杂项目全量同步")
    db = KnowledgeDatabase(TEST_DB)
    reg = ParserRegistry().create_default_registry()
    engine = UpdateEngine(TEST_DIR, db, reg, debounce_window=0)

    result = engine.full_sync()
    log("全量同步完成", result is not None)
    log("同步文件数>0", result.get("total", 0) > 0, f"total={result.get('total')}")
    log("成功数>0", result.get("updated", 0) > 0, f"updated={result.get('updated')}")

    stats = db.get_statistics()
    log("类型数>0", stats["total_types"] > 0, f"types={stats['total_types']}")
    log("函数数>0", stats["total_functions"] > 0, f"funcs={stats['total_functions']}")
    db.close()


def test_02_cross_file_refs():
    """测试2: 跨文件引用（含循环依赖）"""
    print("\n🔍 测试2: 跨文件引用")
    db = KnowledgeDatabase(TEST_DB)
    conn = db._get_connection()

    refs = conn.execute("""
        SELECT r.kind, t1.name as fn, f1.path as ff, t2.name as tn, f2.path as tf
        FROM code_references r
        JOIN types t1 ON r.from_id = t1.id JOIN files f1 ON t1.file_id = f1.id
        JOIN types t2 ON r.to_id = t2.id JOIN files f2 ON t2.file_id = f2.id
        WHERE f1.path != f2.path
    """).fetchall()

    log("跨文件引用数>0", len(refs) > 0, f"count={len(refs)}")
    kinds = {}
    for r in refs:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    log("存在import引用", kinds.get("import", 0) > 0, f"import={kinds.get('import', 0)}")

    # 同文件inherit
    same_inherit = conn.execute("""
        SELECT COUNT(*) FROM code_references r
        JOIN types t1 ON r.from_id = t1.id JOIN files f1 ON t1.file_id = f1.id
        JOIN types t2 ON r.to_id = t2.id JOIN files f2 ON t2.file_id = f2.id
        WHERE r.kind = 'inherit'
    """).fetchone()[0]
    log("存在inherit引用", same_inherit > 0, f"inherit={same_inherit}")
    db.close()


def test_03_checkpoint_phase2_recovery():
    """测试3: 检查点phase=2恢复（BUG-R21-CORE-001验证）"""
    print("\n🔍 测试3: 检查点phase=2恢复")
    # 使用独立数据库，避免影响后续测试
    test3_db = os.path.join(TEST_DIR, "test3_checkpoint.db")
    if os.path.exists(test3_db):
        os.remove(test3_db)

    db = KnowledgeDatabase(test3_db)
    reg = ParserRegistry().create_default_registry()
    engine = UpdateEngine(TEST_DIR, db, reg, debounce_window=0)

    # 模拟phase=2检查点
    import json
    all_files = []
    for root, _, fnames in os.walk(TEST_DIR):
        for f in fnames:
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.py', '.java', '.js'):
                all_files.append(os.path.join(root, f))

    checkpoint_data = {
        "timestamp": "2026-01-01T00:00:00",
        "project_path": engine.project_path,
        "total_files": len(all_files),
        "processed_count": len(all_files),
        "processed_files": all_files,
        "phase": 2
    }
    cp_path = engine._checkpoint_path
    with open(cp_path, 'w') as f:
        json.dump(checkpoint_data, f)

    # 测试_can_resume_from_checkpoint
    can_resume, files_to_process, processed = engine._can_resume_from_checkpoint(
        checkpoint_data, all_files
    )
    log("phase=2恢复返回True", can_resume is True, f"can_resume={can_resume}")
    log("phase=2无待处理文件", len(files_to_process) == 0, f"to_process={len(files_to_process)}")
    log("phase=2保留已处理文件", len(processed) == len(all_files), f"processed={len(processed)}")

    # 清理检查点
    engine._clear_checkpoint()
    db.close()


def test_04_dependency_graph_cte():
    """测试4: CTE优化后的依赖图查询"""
    print("\n🔍 测试4: CTE优化依赖图查询")
    db = KnowledgeDatabase(TEST_DB)

    start = time.time()
    dep = db.get_dependency_graph()
    elapsed = time.time() - start

    log("查询<1秒", elapsed < 1.0, f"elapsed={elapsed:.3f}s")
    log("节点>0", len(dep["nodes"]) > 0, f"nodes={len(dep['nodes'])}")
    log("边>0", len(dep["edges"]) > 0, f"edges={len(dep['edges'])}")
    db.close()


def test_05_nested_calls_no_duplicate():
    """测试5: 嵌套函数调用不重复归属（BUG-R21-PARSER-001验证）"""
    print("\n🔍 测试5: 嵌套函数调用归属")
    parser = PythonParser()
    result = parser.parse_file(os.path.join(TEST_DIR, "src/edge/nested_calls.py"))

    if result and result.calls:
        # outer函数体直接包含helper()调用，所以outer->helper是正确的
        # deepest也调用helper()，所以helper的调用者应包含outer和deepest
        helper_callers = [c.caller for c in result.calls if c.callee == "helper"]
        log("helper被outer和deepest调用", set(helper_callers) == {"outer", "deepest"},
            f"callers={helper_callers}")
        # inner不应调用helper（inner只调用deepest）
        inner_calls = [c.callee for c in result.calls if c.caller == "inner"]
        log("inner只调用deepest", inner_calls == ["deepest"],
            f"inner_callees={inner_calls}")
    else:
        log("解析结果存在", False, "result or calls is None")


def test_06_foreign_key_cascade():
    """测试6: 外键级联删除"""
    print("\n🔍 测试6: 外键级联删除")
    db = KnowledgeDatabase(TEST_DB)
    conn = db._get_connection()

    file_row = conn.execute("""
        SELECT f.id, f.path, COUNT(fn.id) as fc
        FROM files f LEFT JOIN functions fn ON fn.file_id = f.id
        GROUP BY f.id HAVING fc > 0 LIMIT 1
    """).fetchone()

    if not file_row:
        log("找到有函数的文件", False, "no files with functions")
        db.close()
        return

    fid = file_row["id"]
    funcs_before = conn.execute("SELECT COUNT(*) FROM functions WHERE file_id=?", (fid,)).fetchone()[0]

    db.delete_file_cascade(fid)
    db.commit()

    funcs_after = conn.execute("SELECT COUNT(*) FROM functions WHERE file_id=?", (fid,)).fetchone()[0]
    file_exists = conn.execute("SELECT COUNT(*) FROM files WHERE id=?", (fid,)).fetchone()[0]

    log("文件已删除", file_exists == 0)
    log("函数已级联删除", funcs_after == 0, f"before={funcs_before}")
    db.close()


def test_07_concurrent_with_retry():
    """测试7: 并发写入（带重试）"""
    print("\n🔍 测试7: 并发写入压力")
    db = KnowledgeDatabase(TEST_DB)
    reg = ParserRegistry().create_default_registry()

    errors = []
    success = [0]
    lock = threading.Lock()

    def write_file(idx):
        try:
            engine = UpdateEngine(TEST_DIR, db, reg, debounce_window=0)
            fp = os.path.join(TEST_DIR, f"concurrent_{idx}.py")
            with open(fp, 'w') as f:
                f.write(f"class C{idx}:\n    def m(self): pass\n")
            for attempt in range(5):
                try:
                    engine._update_single_file(fp, "created")
                    break
                except Exception as e:
                    if "database is locked" in str(e) and attempt < 4:
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    raise
            os.remove(fp)
            with lock:
                success[0] += 1
        except Exception as e:
            with lock:
                errors.append(str(e))

    threads = [threading.Thread(target=write_file, args=(i,)) for i in range(20)]
    start = time.time()
    for t in threads: t.start()
    for t in threads: t.join(timeout=60)
    elapsed = time.time() - start

    log("无崩溃", len(errors) == 0, f"errors={len(errors)}")
    log("全部成功", success[0] == 20, f"success={success[0]}/20")
    log("完成<60秒", elapsed < 60, f"elapsed={elapsed:.1f}s")
    db.close()


def test_08_data_consistency():
    """测试8: 数据一致性（无悬空引用）"""
    print("\n🔍 测试8: 数据一致性")
    db = KnowledgeDatabase(TEST_DB)
    conn = db._get_connection()

    # 检查calls悬空
    dangling = conn.execute("""
        SELECT c.caller_id FROM calls c
        LEFT JOIN functions f ON c.caller_id = f.id WHERE f.id IS NULL
        UNION
        SELECT c.callee_id FROM calls c
        LEFT JOIN functions f ON c.callee_id = f.id WHERE f.id IS NULL
    """).fetchall()
    log("calls无悬空", len(dangling) == 0, f"dangling={len(dangling)}")

    # 检查references悬空
    dangling_refs = conn.execute("""
        SELECT r.from_id FROM code_references r
        LEFT JOIN types t ON r.from_id = t.id
        LEFT JOIN functions f ON r.from_id = f.id
        WHERE t.id IS NULL AND f.id IS NULL
    """).fetchall()
    log("references无悬空from", len(dangling_refs) == 0, f"dangling={len(dangling_refs)}")

    # 图谱数据一致性
    graph = db.get_graph_data()
    node_ids = set(n["id"] for n in graph["nodes"])
    dangling_edges = [e for e in graph["edges"]
                      if e["source"] not in node_ids or e["target"] not in node_ids]
    log("图谱无悬空边", len(dangling_edges) == 0, f"dangling_edges={len(dangling_edges)}")

    # 数据库完整性
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    log("数据库完整性ok", integrity == "ok", f"integrity={integrity}")

    db.close()


def test_09_temp_table_cleanup():
    """测试9: 临时表在异常路径下被清理"""
    print("\n🔍 测试9: 临时表清理")
    db = KnowledgeDatabase(TEST_DB)
    conn = db._get_connection()

    # 检查是否存在残留的临时表（以_backup、_sync、_checkpoint开头的表）
    all_tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    temp_tables = [t["name"] for t in all_tables
                   if t["name"].startswith("_backup_") or t["name"].startswith("_sync_")
                   or t["name"].startswith("_checkpoint")]
    log("无残留临时表", len(temp_tables) == 0, f"tables={temp_tables}")
    db.close()


def test_10_statistics_accuracy():
    """测试10: 统计数据准确性"""
    print("\n🔍 测试10: 统计准确性")
    db = KnowledgeDatabase(TEST_DB)
    conn = db._get_connection()

    stats = db.get_statistics()
    actual_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    actual_types = conn.execute("SELECT COUNT(*) FROM types").fetchone()[0]
    actual_funcs = conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]

    log("文件数一致", stats["total_files"] == actual_files,
        f"stats={stats['total_files']}, actual={actual_files}")
    log("类型数一致", stats["total_types"] == actual_types,
        f"stats={stats['total_types']}, actual={actual_types}")
    log("函数数一致", stats["total_functions"] == actual_funcs,
        f"stats={stats['total_functions']}, actual={actual_funcs}")
    db.close()


def test_11_java_regex_performance():
    """测试11: Java解析器正则性能（BUG-R21-PARSER-002验证）"""
    print("\n🔍 测试11: Java解析器正则性能")
    # 创建一个包含超长行的Java文件
    long_line_file = os.path.join(TEST_DIR, "src/java/LongLines.java")
    with open(long_line_file, 'w') as f:
        f.write("package src.java;\n")
        for i in range(100):
            # 600字符的注释行
            f.write("// " + "x" * 590 + "\n")
        f.write("public class LongLines {\n")
        f.write("    public void normalMethod() {}\n")
        f.write("}\n")

    parser = JavaParser()
    start = time.time()
    result = parser.parse_file(long_line_file)
    elapsed = time.time() - start

    log("解析超长行<1秒", elapsed < 1.0, f"elapsed={elapsed:.3f}s")
    log("解析结果存在", result is not None)
    if result:
        types = [t for t in result.types if t.name == "LongLines"]
        log("正确提取LongLines类", len(types) == 1, f"found={len(types)}")


def test_12_rapid_changes():
    """测试12: 快速连续变更"""
    print("\n🔍 测试12: 快速连续变更")
    db = KnowledgeDatabase(TEST_DB)
    reg = ParserRegistry().create_default_registry()
    engine = UpdateEngine(TEST_DIR, db, reg, debounce_window=0)

    target = os.path.join(TEST_DIR, "src/models/user.py")
    errors = []
    for i in range(30):
        try:
            with open(target, 'a', encoding='utf-8') as f:
                f.write(f"\n# change {i}\n")
            engine._update_single_file(target, "modified")
        except Exception as e:
            errors.append(str(e))

    log("30次变更无错误", len(errors) == 0, f"errors={len(errors)}")
    conn = db._get_connection()
    user_count = conn.execute("SELECT COUNT(*) FROM types WHERE name='User'").fetchone()[0]
    log("数据一致(User唯一)", user_count == 1, f"count={user_count}")
    db.close()


def run_all():
    global PASS, FAIL, BUGS
    PASS = FAIL = 0
    BUGS = []

    print("=" * 60)
    print("  第21轮 极端复杂场景实战测试")
    print("=" * 60)

    setup()
    try:
        create_complex_project()
        test_01_full_sync_complex()
        test_02_cross_file_refs()
        test_03_checkpoint_phase2_recovery()
        test_04_dependency_graph_cte()
        test_05_nested_calls_no_duplicate()
        test_06_foreign_key_cascade()
        test_07_concurrent_with_retry()
        test_08_data_consistency()
        test_09_temp_table_cleanup()
        test_10_statistics_accuracy()
        test_11_java_regex_performance()
        test_12_rapid_changes()
    finally:
        cleanup()

    print(f"\n{'=' * 60}")
    print(f"  结果: ✅ {PASS} 通过, ❌ {FAIL} 失败")
    print(f"{'=' * 60}")

    if BUGS:
        print("\n🐛 Bug:")
        for n, d in BUGS:
            print(f"  - {n}: {d}")
    else:
        print("\n🎉 全部通过！")

    return FAIL == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
