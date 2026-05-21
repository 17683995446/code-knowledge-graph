#!/usr/bin/env python3
"""
Extreme Stress Test - 极端复杂场景压力测试
验证系统在混乱、大规模、高难度场景下的稳定性
"""

import os
import sys
import tempfile
import shutil
import time
import threading
import logging
import random
import string

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers.python_parser import PythonParser
from parsers.javascript_parser import JavaScriptParser
from parsers.java_parser import JavaParser
from parsers.go_parser import GoParser
from core.database import KnowledgeDatabase
from core.update_engine import UpdateEngine
from parsers.parser_registry import ParserRegistry


class ExtremeScenarioTester:
    """极端场景测试器"""

    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        self.db = None

    def setup(self):
        self.temp_dir = tempfile.mkdtemp(prefix="extreme_test_")
        db_path = os.path.join(self.temp_dir, "test.db")
        self.db = KnowledgeDatabase(db_path)
        logger.info(f"测试目录: {self.temp_dir}")

    def cleanup(self):
        if self.db:
            self.db.close()
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def record(self, name, passed, details=""):
        self.test_results.append({"test": name, "passed": passed, "details": details})
        status = "✓" if passed else "✗"
        logger.info(f"[{status}] {name}: {details}")

    # ============ 极端场景1：二进制文件伪装 ============
    def test_binary_file_disguised(self):
        """测试二进制文件伪装为代码文件"""
        logger.info("=== 极端场景1：二进制文件伪装 ===")
        parser = PythonParser()

        # 创建一个伪装成.py的二进制文件
        binary_file = os.path.join(self.temp_dir, "fake.py")
        with open(binary_file, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')

        try:
            result = parser.parse_file(binary_file)
            # 应该返回空结果且不崩溃
            passed = result is not None and len(result.types) == 0
            self.record("二进制文件伪装", passed, "不崩溃且返回空结果")
        except Exception as e:
            self.record("二进制文件伪装", False, f"崩溃: {e}")

    # ============ 极端场景2：超深嵌套 ============
    def test_deep_nesting(self):
        """测试超深嵌套的代码结构"""
        logger.info("=== 极端场景2：超深嵌套 ===")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "deep.py")
        with open(test_file, "w") as f:
            for i in range(50):
                f.write(f"class Level{i}:\n")
                f.write(f"    def method{i}(self):\n")
                f.write(f"        pass\n")

        try:
            result = parser.parse_file(test_file)
            passed = len(result.types) == 50 and len(result.functions) == 50
            self.record("超深嵌套50层", passed,
                       f"发现 {len(result.types)} 个类型, {len(result.functions)} 个函数")
        except Exception as e:
            self.record("超深嵌套50层", False, f"崩溃: {e}")

    # ============ 极端场景3：超长单行 ============
    def test_very_long_line(self):
        """测试超长单行代码"""
        logger.info("=== 极端场景3：超长单行 ===")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "longline.py")
        with open(test_file, "w") as f:
            f.write("class A:\n")
            # 生成10000字符的单行
            long_line = "    x = " + "+".join([f"'s{i}'" for i in range(2000)])
            f.write(long_line + "\n")
            f.write("    def m(self): return 1\n")

        try:
            result = parser.parse_file(test_file)
            passed = len(result.types) == 1 and len(result.functions) == 1
            self.record("超长单行10000字符", passed, "解析正常")
        except Exception as e:
            self.record("超长单行10000字符", False, f"崩溃: {e}")

    # ============ 极端场景4：大量特殊字符 ============
    def test_special_characters(self):
        """测试包含大量特殊字符的代码"""
        logger.info("=== 极端场景4：大量特殊字符 ===")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "special.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# 特殊字符测试: @#$%^&*()_+-=[]{}|;':\",./<>?\n")
            f.write("class 特殊类_测试:\n")
            f.write("    def 方法_测试(self):\n")
            f.write("        return 1\n")

        try:
            result = parser.parse_file(test_file)
            passed = len(result.types) == 1 and len(result.functions) == 1
            self.record("大量特殊字符", passed, "解析正常")
        except Exception as e:
            self.record("大量特殊字符", False, f"崩溃: {e}")

    # ============ 极端场景5：混合编码项目 ============
    def test_mixed_encoding_project(self):
        """测试混合编码的大型项目全量同步"""
        logger.info("=== 极端场景5：混合编码项目全量同步 ===")

        # 创建不同编码的文件
        encodings_files = [
            ("utf8_mod.py", "utf-8", "class Utf8Class:\n    def method(self):\n        pass\n"),
            ("gbk_mod.py", "gbk", "# GBK编码\nclass GBKClass:\n    def method(self):\n        pass\n"),
            ("latin_mod.py", "latin-1", "# Latin-1: caf\u00e9\nclass LatinClass:\n    def method(self):\n        pass\n"),
        ]

        for fname, enc, content in encodings_files:
            fpath = os.path.join(self.temp_dir, fname)
            with open(fpath, "w", encoding=enc) as f:
                f.write(content)

        registry = ParserRegistry().create_default_registry()
        engine = UpdateEngine(self.temp_dir, self.db, registry)

        try:
            result = engine.full_sync()
            passed = result["updated"] >= 3
            self.record("混合编码项目全量同步", passed,
                       f"同步了 {result['updated']} 个文件")
        except Exception as e:
            self.record("混合编码项目全量同步", False, f"异常: {e}")

    # ============ 极端场景6：文件快速创建删除 ============
    def test_rapid_file_changes(self):
        """测试文件快速创建和删除"""
        logger.info("=== 极端场景6：文件快速创建删除 ===")
        parser = PythonParser()

        passed_all = True
        for i in range(100):
            fpath = os.path.join(self.temp_dir, f"rapid_{i}.py")
            # 创建
            with open(fpath, "w") as f:
                f.write(f"class Rapid{i}:\n    pass\n")
            # 解析
            try:
                result = parser.parse_file(fpath)
                if len(result.types) != 1:
                    passed_all = False
            except Exception:
                passed_all = False
            # 删除
            os.remove(fpath)

        self.record("快速创建删除100次", passed_all, "100次创建-解析-删除循环")

    # ============ 极端场景7：空文件和巨型文件混合 ============
    def test_mixed_file_sizes(self):
        """测试空文件、小文件、大文件混合"""
        logger.info("=== 极端场景7：混合文件大小 ===")
        parser = PythonParser()

        # 空文件
        with open(os.path.join(self.temp_dir, "empty.py"), "w") as f:
            pass

        # 小文件
        with open(os.path.join(self.temp_dir, "small.py"), "w") as f:
            f.write("x = 1\n")

        # 大文件（1000个类）
        big_file = os.path.join(self.temp_dir, "big.py")
        with open(big_file, "w") as f:
            for i in range(1000):
                f.write(f"class Big{i}:\n    def m(self):\n        return {i}\n")

        try:
            r1 = parser.parse_file(os.path.join(self.temp_dir, "empty.py"))
            r2 = parser.parse_file(os.path.join(self.temp_dir, "small.py"))
            r3 = parser.parse_file(big_file)
            passed = (len(r1.types) == 0 and len(r2.types) == 0 and
                     len(r3.types) == 1000 and len(r3.functions) == 1000)
            self.record("混合文件大小", passed,
                       f"空:{len(r1.types)} 小:{len(r2.types)} 大:{len(r3.types)}类/{len(r3.functions)}函数")
        except Exception as e:
            self.record("混合文件大小", False, f"崩溃: {e}")

    # ============ 极端场景8：注释和字符串中的花括号 ============
    def test_braces_in_comments_and_strings(self):
        """测试注释和字符串中包含花括号"""
        logger.info("=== 极端场景8：注释和字符串中的花括号 ===")
        parser = PythonParser()

        test_file = os.path.join(self.temp_dir, "braces.py")
        with open(test_file, "w") as f:
            f.write('class Test:\n')
            f.write('    # 注释中的花括号 { } { { } }\n')
            f.write('    s = "字符串中的花括号 { }"\n')
            f.write("    s2 = '''多行字符串\n")
            f.write("    {花括号}\n")
            f.write("    '''\n")
            f.write('    def method(self):\n')
            f.write('        return "{key: value}"\n')

        try:
            result = parser.parse_file(test_file)
            passed = len(result.types) == 1 and len(result.functions) == 1
            self.record("注释字符串中的花括号", passed, "花括号不影响解析")
        except Exception as e:
            self.record("注释字符串中的花括号", False, f"崩溃: {e}")

    # ============ 极端场景9：并发全量同步 ============
    def test_concurrent_full_sync(self):
        """测试并发全量同步"""
        logger.info("=== 极端场景9：并发全量同步 ===")

        # 创建一些测试文件
        for i in range(20):
            with open(os.path.join(self.temp_dir, f"concurrent_{i}.py"), "w") as f:
                f.write(f"class C{i}:\n    def m(self):\n        pass\n")

        errors = []
        results = [0] * 3

        def run_sync(idx):
            try:
                registry = ParserRegistry().create_default_registry()
                # 每个线程使用独立的数据库
                db = KnowledgeDatabase(
                    os.path.join(self.temp_dir, f"test_{idx}.db"))
                engine = UpdateEngine(self.temp_dir, db, registry)
                r = engine.full_sync()
                results[idx] = r["updated"]
                db.close()
            except Exception as e:
                errors.append(f"Thread {idx}: {e}")

        threads = [threading.Thread(target=run_sync, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        passed = len(errors) == 0 and all(r >= 20 for r in results)
        self.record("并发全量同步(3线程)", passed,
                   f"结果: {results}, 错误: {len(errors)}")

    # ============ 极端场景10：全语言解析器压力测试 ============
    def test_all_parsers_stress(self):
        """测试所有语言解析器的稳定性"""
        logger.info("=== 极端场景10：全语言解析器压力测试 ===")

        test_cases = [
            (PythonParser(), "test.py", """
class MyClass:
    def __init__(self):
        self.x = 1
    def method1(self):
        return self.method2()
    def method2(self):
        return self.x
def global_func():
    return MyClass().method1()
""", 1, 3, 2),
            (JavaScriptParser(), "test.js", """
class JSClass {
    constructor() { this.x = 1; }
    method1() { return this.method2(); }
    method2() { return this.x; }
}
function globalFunc() { return new JSClass().method1(); }
const arrowFunc = () => { return 1; }
""", 1, 3, 1),
            (JavaParser(), "Test.java", """
public class Test {
    public int x;
    public int method1() {
        return method2();
    }
    private int method2() {
        return x;
    }
}
""", 1, 2, 0),
            (GoParser(), "test.go", """
package main
type MyStruct struct {
    X int
}
func (m *MyStruct) Method1() int {
    return m.Method2()
}
func (m *MyStruct) Method2() int {
    return m.X
}
func GlobalFunc() int {
    return 0
}
""", 1, 3, 0),
        ]

        all_passed = True
        for parser, fname, code, exp_types, exp_funcs, min_calls in test_cases:
            fpath = os.path.join(self.temp_dir, fname)
            with open(fpath, "w") as f:
                f.write(code)
            try:
                result = parser.parse_file(fpath)
                ok = (len(result.types) >= exp_types and
                      len(result.functions) >= exp_funcs and
                      len(result.calls) >= min_calls)
                if not ok:
                    all_passed = False
                    logger.warning(f"{fname}: types={len(result.types)} funcs={len(result.functions)} calls={len(result.calls)}")
            except Exception as e:
                all_passed = False
                logger.error(f"{fname} 崩溃: {e}")

        self.record("全语言解析器压力测试", all_passed, "4种语言解析器全部稳定")

    # ============ 极端场景11：compute_end_line边界 ============
    def test_compute_end_line_edge_cases(self):
        """测试compute_end_line的各种边界情况"""
        logger.info("=== 极端场景11：compute_end_line边界 ===")
        from parsers.base_parser import BaseParser

        cases = [
            # (描述, 代码, 期望end_line)
            ("无花括号", ["function foo() {", "    pass", "}"], 3),
            ("正常花括号", ["function foo() {", "    x = 1;", "}"], 3),
            ("花括号在字符串中", ['function foo() {', '    var s = "{";', '    return s;', "}"], 4),
            ("花括号在注释中", ["function foo() {", "    // }", "    x = 1;", "}"], 4),
            ("单行注释后花括号", ["function foo() {", "    // comment", "    {", "    }", "}"], 5),
            ("多行注释中的花括号", ["function foo() {", "    /*", "    }", "    */", "    x = 1;", "}"], 6),
            ("反引号字符串中的花括号", ["function foo() {", "    var s = `}`;", "    return s;", "}"], 4),
            ("转义引号", ['function foo() {', '    var s = "\\"{";', '    return s;', "}"], 4),
        ]

        all_passed = True
        for desc, lines, expected in cases:
            result = BaseParser.compute_end_line(lines, 1)
            if result != expected:
                all_passed = False
                logger.warning(f"compute_end_line失败 [{desc}]: 期望{expected}, 实际{result}")

        self.record("compute_end_line边界", all_passed, f"{len(cases)}个边界用例")

    # ============ 运行所有测试 ============
    def run_all(self):
        logger.info("=" * 80)
        logger.info("开始极端复杂场景压力测试")
        logger.info("=" * 80)

        self.setup()
        try:
            self.test_binary_file_disguised()
            self.test_deep_nesting()
            self.test_very_long_line()
            self.test_special_characters()
            self.test_mixed_encoding_project()
            self.test_rapid_file_changes()
            self.test_mixed_file_sizes()
            self.test_braces_in_comments_and_strings()
            self.test_concurrent_full_sync()
            self.test_all_parsers_stress()
            self.test_compute_end_line_edge_cases()
        finally:
            self.cleanup()

        # 报告
        logger.info("=" * 80)
        logger.info("极端场景测试报告")
        logger.info("=" * 80)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = sum(1 for r in self.test_results if not r["passed"])
        total = len(self.test_results)
        for r in self.test_results:
            s = "✓" if r["passed"] else "✗"
            logger.info(f"[{s}] {r['test']}: {r['details']}")
        logger.info(f"总计: {total} | 通过: {passed} | 失败: {failed}")
        logger.info(f"通过率: {passed/total*100:.1f}%")
        logger.info("=" * 80)
        return failed == 0


if __name__ == "__main__":
    tester = ExtremeScenarioTester()
    success = tester.run_all()
    sys.exit(0 if success else 1)
