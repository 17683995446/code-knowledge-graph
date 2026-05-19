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

    @property
    def language(self) -> str:
        return "java"

    @property
    def file_extensions(self) -> List[str]:
        return [".java"]

    def parse_file(self, file_path: str) -> ParseResult:
        """解析Java文件"""
        result = ParseResult()
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                source_code = fh.read()
            if not source_code.strip():
                return result

            lines = source_code.split("\n")
            self._extract_imports(lines, result)
            self._extract_types(lines, result)
            self._extract_methods(lines, result)
            self._extract_calls(source_code, result)
        except Exception:
            pass
        return result

    def _extract_imports(self, lines: List[str], result: ParseResult):
        """提取import语句"""
        pattern = re.compile(r'import\s+(?:static\s+)?([\w.]+)(?:\.\*)?;')
        for line in lines:
            match = pattern.search(line)
            if match:
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
        """提取类型定义（class/interface/enum）"""
        type_pattern = re.compile(
            r'(?:public|private|protected)?\s*(?:abstract|final|static)?\s*'
            r'(class|interface|enum)\s+(\w+)'
            r'(?:\s+extends\s+(\w+))?'
            r'(?:\s+implements\s+([\w,\s]+))?'
        )
        for line_num, line in enumerate(lines, 1):
            match = type_pattern.search(line)
            if match:
                kind = match.group(1)
                type_name = match.group(2)
                result.types.append(TypeInfo(
                    name=type_name,
                    kind=kind,
                    start_line=line_num,
                    end_line=line_num
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
        """提取方法定义"""
        method_pattern = re.compile(
            r'(?:public|private|protected)?\s*(?:static|final|abstract|synchronized|native)?\s*'
            r'(?:[\w<>\[\],\s]+)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{?'
        )
        current_class = ""
        for line_num, line in enumerate(lines, 1):
            class_match = re.search(r'(?:class|interface|enum)\s+(\w+)', line)
            if class_match:
                current_class = class_match.group(1)

            method_match = method_pattern.search(line)
            if method_match:
                method_name = method_match.group(1)
                skip_words = {
                    "if", "for", "while", "switch", "catch", "return",
                    "new", "class", "interface", "enum", "import", "package",
                    "public", "private", "protected", "static", "final",
                    "abstract", "synchronized", "void"
                }
                if method_name not in skip_words and not method_name[0].isupper():
                    result.functions.append(FunctionInfo(
                        name=method_name,
                        type_name=current_class or "__module__",
                        start_line=line_num,
                        end_line=line_num
                    ))

    def _extract_calls(self, source_code: str, result: ParseResult):
        """提取方法调用关系
        BUG-JP-01修复：只在方法体范围内查找调用
        """
        lines = source_code.split('\n')
        func_names = {f.name for f in result.functions}
        call_pattern = re.compile(r'(\w+)\s*\(')
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
            end = func_info.end_line or start + 50
            search_text = '\n'.join(lines[max(0, start - 1):min(len(lines), end)])
            matches = call_pattern.findall(search_text)
            for callee in matches:
                if callee in func_names and callee != caller and callee not in skip_words:
                    call_set.add((caller, callee))

        for caller, callee in call_set:
            result.calls.append(CallInfo(caller=caller, callee=callee))
