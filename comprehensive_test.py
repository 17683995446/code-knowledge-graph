#!/usr/bin/env python3
"""
Comprehensive Test - 代码知识图谱系统全面测试
验证所有修复和边界情况
"""

import os
import sys
import tempfile
import asyncio
import time
import logging
from pathlib import Path

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('comprehensive_test.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers.python_parser import PythonParser
from parsers.javascript_parser import JavaScriptParser
from parsers.java_parser import JavaParser
from parsers.go_parser import GoParser
from core.database import KnowledgeDatabase
from core.update_engine import UpdateEngine
from parsers.parser_registry import ParserRegistry
from debug_logger import setup_debug_logging, log_checkpoint


class ComprehensiveTester:
    """全面测试器"""

    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        self.db = None

    def setup(self):
        """设置测试环境"""
        log_checkpoint(__name__, "测试环境设置")
        self.temp_dir = tempfile.mkdtemp(prefix="code_knowledge_test_")
        db_path = os.path.join(self.temp_dir, "test.db")
        self.db = KnowledgeDatabase(db_path)
        logger.info(f"测试环境: temp_dir={self.temp_dir}, db={db_path}")

    def cleanup(self):
        """清理测试环境"""
        log_checkpoint(__name__, "测试环境清理")
        if self.db:
            self.db.close()
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
        logger.info("测试环境已清理")

    def record_result(self, test_name: str, passed: bool, details: str = ""):
        """记录测试结果"""
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"[{status}] {test_name}: {details}")

    # ============ 编码测试 ============
    def test_encoding_utf8(self):
        """测试UTF-8编码文件解析"""
        log_checkpoint(__name__, "测试UTF-8编码")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "utf8_test.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('# -*- coding: utf-8 -*-\n')
            f.write('class 测试类:\n')
            f.write('    def 测试方法(self):\n')
            f.write('        pass\n')

        result = parser.parse_file(test_file)
        passed = len(result.types) == 1 and len(result.functions) == 1
        self.record_result("编码测试-UTF8", passed,
                          f"发现 {len(result.types)} 个类型, {len(result.functions)} 个函数")

    def test_encoding_gbk(self):
        """测试GBK编码文件解析"""
        log_checkpoint(__name__, "测试GBK编码")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "gbk_test.py")
        with open(test_file, "w", encoding="gbk") as f:
            f.write('# GBK编码测试\n')
            f.write('class GBKClass:\n')
            f.write('    def gbk_method(self):\n')
            f.write('        pass\n')

        result = parser.parse_file(test_file)
        passed = len(result.types) == 1 and len(result.functions) == 1
        self.record_result("编码测试-GBK", passed,
                          f"发现 {len(result.types)} 个类型, {len(result.functions)} 个函数")

    def test_encoding_latin1(self):
        """测试Latin-1编码文件解析"""
        log_checkpoint(__name__, "测试Latin-1编码")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "latin1_test.py")
        with open(test_file, "w", encoding="latin-1") as f:
            f.write('# Latin-1: café résumé\n')
            f.write('class LatinClass:\n')
            f.write('    def latin_method(self):\n')
            f.write('        pass\n')

        result = parser.parse_file(test_file)
        passed = len(result.types) == 1 and len(result.functions) == 1
        self.record_result("编码测试-Latin1", passed,
                          f"发现 {len(result.types)} 个类型, {len(result.functions)} 个函数")

    # ============ 边界条件测试 ============
    def test_empty_file(self):
        """测试空文件"""
        log_checkpoint(__name__, "测试空文件")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "empty.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('')

        result = parser.parse_file(test_file)
        passed = len(result.types) == 0 and len(result.functions) == 0
        self.record_result("边界测试-空文件", passed, "空文件解析正常")

    def test_whitespace_only_file(self):
        """测试仅空白字符文件"""
        log_checkpoint(__name__, "测试空白文件")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "whitespace.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('   \n\n   \n')

        result = parser.parse_file(test_file)
        passed = len(result.types) == 0 and len(result.functions) == 0
        self.record_result("边界测试-空白文件", passed, "空白文件解析正常")

    def test_syntax_error_file(self):
        """测试语法错误文件"""
        log_checkpoint(__name__, "测试语法错误文件")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "syntax_error.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('class Test:\n')
            f.write('    def method(self)\n')  # 缺少冒号
            f.write('        pass\n')

        result = parser.parse_file(test_file)
        # 应该返回空结果但不崩溃
        passed = result is not None
        self.record_result("边界测试-语法错误", passed, "语法错误文件处理正常")

    def test_very_long_file(self):
        """测试超长文件"""
        log_checkpoint(__name__, "测试超长文件")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "long_file.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('class LongClass:\n')
            for i in range(1000):
                f.write(f'    def method_{i}(self):\n')
                f.write(f'        return {i}\n')

        result = parser.parse_file(test_file)
        passed = len(result.functions) == 1000
        self.record_result("边界测试-超长文件", passed,
                          f"发现 {len(result.functions)} 个函数 (期望1000)")

    # ============ 跨文件引用测试 ============
    def test_cross_file_references(self):
        """测试跨文件引用"""
        log_checkpoint(__name__, "测试跨文件引用")

        # 创建测试文件
        file1 = os.path.join(self.temp_dir, "module_a.py")
        with open(file1, "w", encoding="utf-8") as f:
            f.write('class BaseClass:\n')
            f.write('    def base_method(self):\n')
            f.write('        pass\n')

        file2 = os.path.join(self.temp_dir, "module_b.py")
        with open(file2, "w", encoding="utf-8") as f:
            f.write('from module_a import BaseClass\n')
            f.write('class DerivedClass(BaseClass):\n')
            f.write('    def derived_method(self):\n')
            f.write('        self.base_method()\n')

        # 执行全量同步
        registry = ParserRegistry().create_default_registry()
        engine = UpdateEngine(self.temp_dir, self.db, registry)

        try:
            result = engine.full_sync()
            passed = result["updated"] >= 2
            self.record_result("跨文件引用测试", passed,
                              f"同步了 {result['updated']} 个文件")
        except Exception as e:
            self.record_result("跨文件引用测试", False, f"异常: {e}")

    # ============ 并发测试 ============
    def test_concurrent_access(self):
        """测试并发访问"""
        log_checkpoint(__name__, "测试并发访问")

        import threading

        errors = []
        success_count = [0]

        def worker(worker_id):
            try:
                for i in range(10):
                    file_path = os.path.join(self.temp_dir, f"concurrent_{worker_id}_{i}.py")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(f'class Worker{worker_id}Class{i}:\n')
                        f.write('    pass\n')

                    # 计算文件哈希
                    self.db.compute_file_hash(file_path)
                    success_count[0] += 1
            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        passed = len(errors) == 0 and success_count[0] == 50
        self.record_result("并发测试", passed,
                          f"成功 {success_count[0]}/50, 错误: {len(errors)}")

    # ============ 数据库事务测试 ============
    def test_transaction_rollback(self):
        """测试事务回滚"""
        log_checkpoint(__name__, "测试事务回滚")

        try:
            # 开始事务
            conn = self.db._get_connection()

            # 插入测试数据
            conn.execute("INSERT INTO files (path, language, hash, modified) VALUES (?, ?, ?, ?)",
                        ("/test/file.py", "python", b"hash", 0))

            # 回滚
            self.db.rollback()

            # 验证数据不存在
            row = conn.execute("SELECT * FROM files WHERE path = ?", ("/test/file.py",)).fetchone()
            passed = row is None

            self.record_result("事务回滚测试", passed, "回滚后数据不存在")
        except Exception as e:
            self.record_result("事务回滚测试", False, f"异常: {e}")

    def test_transaction_commit(self):
        """测试事务提交"""
        log_checkpoint(__name__, "测试事务提交")

        try:
            # 插入测试数据
            conn = self.db._get_connection()
            conn.execute("INSERT INTO files (path, language, hash, modified) VALUES (?, ?, ?, ?)",
                        ("/test/commit.py", "python", b"hash", 0))

            # 提交
            self.db.commit()

            # 验证数据存在
            row = conn.execute("SELECT * FROM files WHERE path = ?", ("/test/commit.py",)).fetchone()
            passed = row is not None

            self.record_result("事务提交测试", passed, "提交后数据存在")
        except Exception as e:
            self.record_result("事务提交测试", False, f"异常: {e}")

    # ============ 解析器测试 ============
    def test_javascript_parser(self):
        """测试JavaScript解析器"""
        log_checkpoint(__name__, "测试JavaScript解析器")
        parser = JavaScriptParser()

        test_file = os.path.join(self.temp_dir, "test.js")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('class MyClass {\n')
            f.write('    constructor() {}\n')
            f.write('    myMethod() {}\n')
            f.write('}\n')
            f.write('function globalFunc() {}\n')

        result = parser.parse_file(test_file)
        passed = len(result.types) >= 1 and len(result.functions) >= 2
        self.record_result("JS解析器测试", passed,
                          f"发现 {len(result.types)} 个类型, {len(result.functions)} 个函数")

    def test_java_parser(self):
        """测试Java解析器"""
        log_checkpoint(__name__, "测试Java解析器")
        parser = JavaParser()

        test_file = os.path.join(self.temp_dir, "Test.java")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('public class Test {\n')
            f.write('    public void method1() {}\n')
            f.write('    private int method2() { return 0; }\n')
            f.write('}\n')

        result = parser.parse_file(test_file)
        passed = len(result.types) >= 1 and len(result.functions) >= 2
        self.record_result("Java解析器测试", passed,
                          f"发现 {len(result.types)} 个类型, {len(result.functions)} 个函数")

    def test_go_parser(self):
        """测试Go解析器"""
        log_checkpoint(__name__, "测试Go解析器")
        parser = GoParser()

        test_file = os.path.join(self.temp_dir, "test.go")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('package main\n')
            f.write('type MyStruct struct {}\n')
            f.write('func (m *MyStruct) Method() {}\n')
            f.write('func GlobalFunc() {}\n')

        result = parser.parse_file(test_file)
        passed = len(result.types) >= 1 and len(result.functions) >= 2
        self.record_result("Go解析器测试", passed,
                          f"发现 {len(result.types)} 个类型, {len(result.functions)} 个函数")

    # ============ 运行所有测试 ============
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 80)
        logger.info("开始全面测试")
        logger.info("=" * 80)

        self.setup()

        try:
            # 编码测试
            self.test_encoding_utf8()
            self.test_encoding_gbk()
            self.test_encoding_latin1()

            # 边界条件测试
            self.test_empty_file()
            self.test_whitespace_only_file()
            self.test_syntax_error_file()
            self.test_very_long_file()

            # 跨文件引用测试
            self.test_cross_file_references()

            # 并发测试
            self.test_concurrent_access()

            # 事务测试
            self.test_transaction_rollback()
            self.test_transaction_commit()

            # 解析器测试
            self.test_javascript_parser()
            self.test_java_parser()
            self.test_go_parser()

        finally:
            self.cleanup()

        # 输出测试报告
        self.print_report()

    def print_report(self):
        """打印测试报告"""
        logger.info("=" * 80)
        logger.info("测试报告")
        logger.info("=" * 80)

        passed = sum(1 for r in self.test_results if r["passed"])
        failed = sum(1 for r in self.test_results if not r["passed"])
        total = len(self.test_results)

        for result in self.test_results:
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            logger.info(f"[{status}] {result['test']}: {result['details']}")

        logger.info("-" * 80)
        logger.info(f"总计: {total} | 通过: {passed} | 失败: {failed}")
        logger.info(f"通过率: {passed/total*100:.1f}%" if total > 0 else "N/A")
        logger.info("=" * 80)

        return failed == 0


if __name__ == "__main__":
    setup_debug_logging(logging.DEBUG)
    tester = ComprehensiveTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)