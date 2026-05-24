"""
Java Parser - Java语言解析器
基于正则表达式的轻量级解析器，支持Java类、接口、枚举、方法
"""

import re
from typing import List

from parsers.base_parser import (
    BaseParser, ParseResult, TypeInfo, FunctionInfo,
    CallInfo, ReferenceInfo
)


class JavaParser(BaseParser):
    """
    Java代码解析器
    基于正则表达式，支持class/interface/enum/method/import
    """

    # BUG-JAVA-REGEX-01修复：将正则表达式编译为类变量，避免重复编译
    IMPORT_PATTERN = re.compile(r'import\s+(?:static\s+)?([\w.]+)(\.\*)?;')
    TYPE_PATTERN = re.compile(
        r'(?:public|private|protected)?\s*(?:abstract|final|static)?\s*'
        r'(class|interface|enum)\s+(\w+)'
        r'(?:\s+extends\s+(\w+))?'
        r'(?:\s+implements\s+([\w,\s]+))?'
    )
    METHOD_PATTERN = re.compile(
        r'^\s*(?:public|private|protected)?\s*(?:static|final|abstract|synchronized|native)?\s*'
        r'(?:[\w<>\[\],\s]{1,60})\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*(?:\{?|$)'
    )
    CALL_PATTERN = re.compile(r'(\w+)\s*\(')

    @property
    def language(self) -> str:
        return "java"

    @property
    def file_extensions(self) -> List[str]:
        return [".java"]

    def parse_file(self, file_path: str) -> ParseResult:
        """解析Java文件
        BUG-JAVA-02修复：尝试多种编码，添加异常日志
        BUG-PARSER-INPUT-003修复：添加文件大小检查
        """
        result = ParseResult()
        
        # BUG-PARSER-INPUT-003修复：检查文件大小
        if not self.check_file_size(file_path):
            return result
        
        # BUG-R21-PARSER-005修复：使用BaseParser公共方法读取文件内容
        source_code = self._read_file_content(file_path)
        if source_code is None:
            return result

        try:
            if not source_code.strip():
                return result

            lines = source_code.split("\n")
            self._extract_imports(lines, result)
            self._extract_types(lines, result)
            self._extract_methods(lines, result)
            self._extract_calls(source_code, result)
        except Exception as e:
            # BUG-JAVA-02修复：添加异常日志
            import logging
            logging.getLogger(__name__).warning(f"Java解析失败 {file_path}: {e}")
        return result

    def _extract_imports(self, lines: List[str], result: ParseResult):
        """提取import语句
        BUG-JAVA-WILDCARD-01修复：跳过通配符导入(.*)
        BUG-JAVA-REGEX-01修复：使用类变量中的预编译正则
        """
        for line in lines:
            match = self.IMPORT_PATTERN.search(line)
            if match:
                # BUG-JAVA-WILDCARD-01修复：跳过通配符导入
                if match.group(2):  # 检测到.*
                    continue
                full_path = match.group(1)
                parts = full_path.split(".")
                if len(parts) >= 2:
                    class_name = parts[-1]
                    package = parts[0]
                    result.references.append(ReferenceInfo(
                        from_entity="__module__",
                        to_entity=class_name,
                        kind="import"
                    ))

    def _extract_types(self, lines: List[str], result: ParseResult):
        """提取类型定义（class/interface/enum）
        BUG-STR-LIT-01修复：跳过字符串和注释中的内容
        BUG-JAVA-REGEX-01修复：使用类变量中的预编译正则
        """
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            # 跳过注释和字符串行
            if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
                continue
            # 跳过字符串字面量行（简单启发式）
            if stripped.startswith('"') or stripped.startswith("'"):
                continue

            match = self.TYPE_PATTERN.search(line)
            if match:
                # BUG-STR-LIT-01: 检查匹配是否在字符串字面量内
                if self._is_inside_string(line, match.start()):
                    continue
                kind = match.group(1)
                type_name = match.group(2)
                type_end = self.compute_end_line(lines, line_num)
                result.types.append(TypeInfo(
                    name=type_name,
                    kind=kind,
                    start_line=line_num,
                    end_line=type_end
                ))
                if match.group(3):
                    result.references.append(ReferenceInfo(
                        from_entity=type_name,
                        to_entity=match.group(3),
                        kind="inherit"
                    ))
                if match.group(4):
                    for iface in match.group(4).split(","):
                        iface_name = iface.strip()
                        if iface_name:
                            result.references.append(ReferenceInfo(
                                from_entity=type_name,
                                to_entity=iface_name,
                                kind="implement"
                            ))

    def _extract_methods(self, lines: List[str], result: ParseResult):
        """提取方法定义
        BUG-FUNC-DUP-02修复：使用compute_end_line正确计算范围
        BUG-STR-LIT-01修复：跳过字符串和注释，检查匹配是否在引号内
        BUG-JAVA-03修复：放宽方法匹配正则，支持方法体在下一行
        BUG-JAVA-REGEX-01修复：使用类变量中的预编译正则
        """
        current_class = ""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
                continue

            # BUG-R21-PARSER-002修复：快速预检查，跳过不含括号的行
            if '(' not in line:
                continue
            # 跳过过长的行（>500字符），避免正则回溯
            if len(line) > 500:
                continue

            class_match = re.search(r'(?:class|interface|enum)\s+(\w+)', line)
            if class_match:
                current_class = class_match.group(1)

            method_match = self.METHOD_PATTERN.search(line)
            if method_match:
                method_name = method_match.group(1)
                skip_words = {
                    "if", "for", "while", "switch", "catch", "return",
                    "new", "class", "interface", "enum", "import", "package",
                    "public", "private", "protected", "static", "final",
                    "abstract", "synchronized", "void", "extends", "implements"
                }
                # BUG-JAVA-03修复：更严格的过滤条件
                if method_name in skip_words:
                    continue
                # BUG-JAVA-UPPER-01修复：不再按首字母大写过滤方法
                # 原逻辑会错误过滤构造函数、测试方法等合法方法
                # 改为检查是否为Java关键字（已在skip_words中）
                # 排除纯数字
                if method_name.isdigit():
                    continue
                # BUG-STR-LIT-01: 检查匹配位置是否在字符串字面量内
                match_pos = method_match.start()
                if self._is_inside_string(line, match_pos):
                    continue
                method_end = self.compute_end_line(lines, line_num)
                result.functions.append(FunctionInfo(
                    name=method_name,
                    type_name=current_class or "__module__",
                    start_line=line_num,
                    end_line=method_end
                ))

    @staticmethod
    def _is_inside_string(line: str, pos: int) -> bool:
        """检查给定位置是否在字符串字面量内"""
        in_string = False
        i = 0
        while i < pos:
            ch = line[i]
            if ch == '\\':
                i += 2
                continue
            if ch == '"':
                in_string = not in_string
            i += 1
        return in_string

    def _extract_calls(self, source_code: str, result: ParseResult):
        """提取方法调用关系
        BUG-JP-01修复：只在方法体范围内查找调用
        BUG-JAVA-REGEX-01修复：使用类变量中的预编译正则
        """
        lines = source_code.split('\n')
        func_names = {f.name for f in result.functions}
        skip_words = {
            "if", "for", "while", "switch", "catch", "return", "new",
            "class", "interface", "enum", "import", "package", "super",
            "this", "null", "true", "false", "else", "try", "throw",
            "throws", "instanceof", "public", "private", "protected",
            "static", "final", "abstract", "void", "int", "String",
            "boolean", "long", "double", "float", "char", "byte", "short"
        }
        call_set = set()
        for func_info in result.functions:
            caller = func_info.name
            start = func_info.start_line or 0
            # BUG-SYS-004修复：当end_line等于start_line时，使用默认范围
            end = func_info.end_line
            if end <= start:
                end = start + 100
            search_text = '\n'.join(lines[max(0, start - 1):min(len(lines), end)])
            matches = self.CALL_PATTERN.findall(search_text)
            for callee in matches:
                if callee in func_names and callee != caller and callee not in skip_words:
                    call_set.add((caller, callee))

        for caller, callee in call_set:
            result.calls.append(CallInfo(caller=caller, callee=callee))
