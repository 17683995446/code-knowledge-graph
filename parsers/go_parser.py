"""
Go Parser - Go语言解析器
基于正则表达式的轻量级解析器，支持struct/interface/func/import
"""

import re
from typing import List

from parsers.base_parser import (
    BaseParser, ParseResult, TypeInfo, FunctionInfo,
    CallInfo, ReferenceInfo
)


class GoParser(BaseParser):
    """
    Go代码解析器
    基于正则表达式，支持struct/interface/func/import
    """

    @property
    def language(self) -> str:
        return "go"

    @property
    def file_extensions(self) -> List[str]:
        return [".go"]

    def parse_file(self, file_path: str) -> ParseResult:
        """解析Go文件
        BUG-GO-02修复：尝试多种编码，添加异常日志
        """
        result = ParseResult()
        source_code = None

        # BUG-GO-02修复：尝试多种编码
        encodings = ["utf-8", "gbk", "gb2312", "latin-1", "cp1252"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as fh:
                    source_code = fh.read()
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                continue

        # 如果所有编码都失败，使用errors='ignore'作为最后手段
        if source_code is None:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    source_code = fh.read()
            except Exception as e:
                return result

        try:
            if not source_code.strip():
                return result

            lines = source_code.split("\n")
            self._extract_imports(lines, result)
            self._extract_types(lines, result)
            self._extract_functions(lines, result)
            self._extract_calls(source_code, result)
        except Exception as e:
            # BUG-GO-02修复：添加异常日志
            import logging
            logging.getLogger(__name__).warning(f"Go解析失败 {file_path}: {e}")
        return result

    def _extract_imports(self, lines: List[str], result: ParseResult):
        """提取import语句"""
        in_import_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ("):
                in_import_block = True
                continue
            if in_import_block:
                if stripped == ")":
                    in_import_block = False
                    continue
                import_match = re.search(r'(?:"([^"]+)"|\'([^\']+)\')', stripped)
                if import_match:
                    module_path = import_match.group(1) or import_match.group(2)
                    alias_match = re.match(r'(\w+)\s+', stripped)
                    alias = alias_match.group(1) if alias_match else ""
                    module_name = module_path.split("/")[-1]
                    result.references.append(ReferenceInfo(
                        from_entity=alias or module_name,
                        to_entity=module_name,
                        kind="import"
                    ))
            elif stripped.startswith("import "):
                import_match = re.search(r'"([^"]+)"', stripped)
                if import_match:
                    module_path = import_match.group(1)
                    module_name = module_path.split("/")[-1]
                    result.references.append(ReferenceInfo(
                        from_entity=module_name,
                        to_entity=module_name,
                        kind="import"
                    ))

    def _extract_types(self, lines: List[str], result: ParseResult):
        """提取类型定义（struct/interface）
        BUG-STR-LIT-01修复：跳过字符串和注释中的内容
        """
        type_pattern = re.compile(r'type\s+(\w+)\s+(struct|interface)\b')
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
                continue
            if stripped.startswith('"') or stripped.startswith("'"):
                continue
            match = type_pattern.search(line)
            if match:
                type_name = match.group(1)
                kind = match.group(2)
                type_end = self.compute_end_line(lines, line_num)
                result.types.append(TypeInfo(
                    name=type_name,
                    kind=kind,
                    start_line=line_num,
                    end_line=type_end
                ))

    def _extract_functions(self, lines: List[str], result: ParseResult):
        """提取函数和方法
        BUG-CALL-ALL-01修复：使用compute_end_line正确计算范围
        """
        func_pattern = re.compile(
            r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\('
        )
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
                continue
            if stripped.startswith('"') or stripped.startswith("'"):
                continue
            match = func_pattern.search(line)
            if match:
                func_name = match.group(1)
                receiver_match = re.match(r'\s*func\s+\(([^)]+)\)', line)
                if receiver_match:
                    receiver = receiver_match.group(1).strip().split()[-1].replace("*", "")
                    type_name = receiver
                else:
                    type_name = "__module__"

                func_end = self.compute_end_line(lines, line_num)
                result.functions.append(FunctionInfo(
                    name=func_name,
                    type_name=type_name,
                    start_line=line_num,
                    end_line=func_end
                ))

    def _extract_calls(self, source_code: str, result: ParseResult):
        """提取函数调用关系
        BUG-GP-01修复：只在函数体范围内查找调用
        """
        lines = source_code.split('\n')
        func_names = {f.name for f in result.functions}
        call_pattern = re.compile(r'(\w+)\s*\(')
        skip_words = {
            "if", "for", "range", "switch", "case", "return", "go",
            "defer", "func", "type", "struct", "interface", "import",
            "package", "var", "const", "make", "len", "append",
            "new", "panic", "recover", "print", "println", "fmt",
            "true", "false", "nil", "else", "break", "continue",
            "fallthrough", "default", "map", "chan", "select"
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
            matches = call_pattern.findall(search_text)
            for callee in matches:
                if callee in func_names and callee != caller and callee not in skip_words:
                    call_set.add((caller, callee))

        for caller, callee in call_set:
            result.calls.append(CallInfo(caller=caller, callee=callee))
