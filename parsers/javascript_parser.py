"""
JavaScript Parser - JavaScript/TypeScript语言解析器
基于正则表达式的轻量级解析器，支持ES6+语法
"""

import re
import os
from typing import List, Optional

from parsers.base_parser import (
    BaseParser, ParseResult, TypeInfo, FunctionInfo,
    CallInfo, ReferenceInfo
)


class JavaScriptParser(BaseParser):
    """
    JavaScript/TypeScript代码解析器
    基于正则表达式，支持class/function/arrow/import/export
    """

    @property
    def language(self) -> str:
        return "javascript"

    @property
    def file_extensions(self) -> List[str]:
        return [".js", ".jsx", ".ts", ".tsx"]

    @staticmethod
    def _compute_end_line(lines: List[str], start_line: int) -> int:
        """通过花括号深度追踪计算函数/方法的结束行号
        BUG-CALL-ALL-01修复：正确计算end_line使_extract_calls能覆盖方法体
        BUG-JS-003修复：每行开始时重置单行注释状态
        BUG-BP-002修复：扫描范围扩大到2000行
        BUG-BP-004修复：转义字符j+=2添加边界检查
        """
        depth = 0
        found_first_brace = False
        in_string = None  # 跟踪字符串状态: None, '"', "'", '`'
        in_comment = None  # 跟踪注释状态: None, '//', '/*'

        for i in range(start_line - 1, min(len(lines), start_line + 2000)):
            line = lines[i]
            # BUG-JS-003修复：每行开始时重置单行注释状态
            if in_comment == '//':
                in_comment = None
            j = 0
            while j < len(line):
                ch = line[j]

                # 处理注释
                if in_comment == '//' and ch == '\n':
                    in_comment = None
                    j += 1
                    continue
                if in_comment == '/*' and j + 1 < len(line) and line[j:j+2] == '*/':
                    in_comment = None
                    j += 2
                    continue
                if in_comment is None and j + 1 < len(line):
                    two = line[j:j+2]
                    if two == '//':
                        in_comment = '//'
                        break
                    if two == '/*':
                        in_comment = '/*'
                        j += 2
                        continue

                if in_comment:
                    j += 1
                    continue

                # 处理字符串
                if in_string and ch == '\\':
                    # BUG-BP-004修复：添加边界检查
                    if j + 1 < len(line):
                        j += 2
                    else:
                        j += 1
                    continue
                if in_string and ch == in_string:
                    in_string = None
                    j += 1
                    continue
                if in_string is None and ch in ('"', "'", '`'):
                    in_string = ch
                    j += 1
                    continue

                # 计算花括号深度
                if ch == '{':
                    depth += 1
                    found_first_brace = True
                elif ch == '}':
                    depth -= 1
                    if found_first_brace and depth <= 0:
                        return i + 1  # 返回1-based行号
                j += 1

        return start_line  # 保守返回起始行

    def parse_file(self, file_path: str) -> ParseResult:
        """解析JavaScript/TypeScript文件
        BUG-JS-02修复：尝试多种编码，添加异常日志
        BUG-PARSER-INPUT-003修复：添加文件大小检查
        """
        result = ParseResult()
        
        # BUG-PARSER-INPUT-003修复：检查文件大小
        if not self.check_file_size(file_path):
            return result
        
        source_code = None

        # BUG-JS-02修复：尝试多种编码
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
            self._extract_classes(lines, result)
            self._extract_functions(lines, result)
            self._extract_arrow_functions(lines, result)
            self._extract_imports(lines, result)
            self._extract_calls(source_code, result)
        except Exception as e:
            # BUG-JS-02修复：添加异常日志
            import logging
            logging.getLogger(__name__).warning(f"JS/TS解析失败 {file_path}: {e}")
        return result

    def _extract_classes(self, lines: List[str], result: ParseResult):
        """提取类定义和类方法
        BUG-FUNC-DUP-02修复：使用花括号深度追踪正确计算end_line
        BUG-STR-LIT-01修复：跳过字符串和注释中的内容
        """
        pattern = re.compile(
            r'(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)'
            r'(?:\s+extends\s+(\w+))?'
            r'(?:\s+implements\s+([\w,\s]+))?'
        )
        
        current_class = ""
        class_brace_depth = 0
        in_class = False
        
        for line_num, line in enumerate(lines, 1):
            # 跳过注释行和字符串行
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
                continue
            
            # 检测类定义
            match = pattern.search(line)
            if match:
                class_name = match.group(1)
                current_class = class_name
                in_class = True
                class_brace_depth = line.count('{') - line.count('}')
                
                class_end = self._compute_end_line(lines, line_num)
                result.types.append(TypeInfo(
                    name=class_name,
                    kind="class",
                    start_line=line_num,
                    end_line=class_end
                ))
                if match.group(2):
                    result.references.append(ReferenceInfo(
                        from_entity=class_name,
                        to_entity=match.group(2),
                        kind="inherit"
                    ))
                if match.group(3):
                    for iface in match.group(3).split(","):
                        iface_name = iface.strip()
                        if iface_name:
                            result.references.append(ReferenceInfo(
                                from_entity=class_name,
                                to_entity=iface_name,
                                kind="implement"
                            ))
                continue
            
            # 跟踪类范围
            if in_class:
                class_brace_depth += line.count('{') - line.count('}')
                if class_brace_depth <= 0:
                    in_class = False
                    current_class = ""
                    continue
                
                # 提取类方法（只在类直接子级，缩进恰好2-4空格）
                method_pattern = re.compile(
                    r'^\s{2,4}(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{?'
                )
                method_match = method_pattern.match(line)
                if method_match:
                    method_name = method_match.group(1)
                    skip_words = {"if", "for", "while", "switch", "catch", "return", 
                                 "new", "class", "function", "constructor", "super",
                                 "this", "else", "try", "throw", "typeof", "instanceof"}
                    if method_name not in skip_words and not method_name.startswith('//'):
                        method_end = self._compute_end_line(lines, line_num)
                        result.functions.append(FunctionInfo(
                            name=method_name,
                            type_name=current_class,
                            start_line=line_num,
                            end_line=method_end
                        ))

    def _extract_functions(self, lines: List[str], result: ParseResult):
        """提取函数声明"""
        pattern = re.compile(
            r'(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\('
        )
        for line_num, line in enumerate(lines, 1):
            match = pattern.search(line)
            if match:
                func_name = match.group(1)
                func_end = self._compute_end_line(lines, line_num)
                result.functions.append(FunctionInfo(
                    name=func_name,
                    type_name="__module__",
                    start_line=line_num,
                    end_line=func_end
                ))

    def _extract_arrow_functions(self, lines: List[str], result: ParseResult):
        """提取箭头函数和const函数
        BUG-FUNC-DUP-02修复：跳过已在类中提取的方法
        """
        existing_names = {f.name for f in result.functions}
        pattern = re.compile(
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?'
            r'(?:\([^)]*\)|\w+)\s*=>'
        )
        for line_num, line in enumerate(lines, 1):
            match = pattern.search(line)
            if match:
                func_name = match.group(1)
                if func_name not in existing_names:
                    func_end = self._compute_end_line(lines, line_num)
                    result.functions.append(FunctionInfo(
                        name=func_name,
                        type_name="__module__",
                        start_line=line_num,
                        end_line=func_end
                    ))

    def _extract_imports(self, lines: List[str], result: ParseResult):
        """提取import语句"""
        import_pattern = re.compile(
            r'import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+[\'"]([^"\']+)[\'"]'
        )
        require_pattern = re.compile(
            r'(?:const|let|var)\s+(\w+)\s*=\s*require\s*\([\'"]([^"\']+)[\'"]\)'
        )
        for line in lines:
            match = import_pattern.search(line)
            if match:
                named_imports = match.group(1)
                default_import = match.group(2)
                module_path = match.group(3)
                module_name = module_path.split("/")[-1].split(".")[0]
                if named_imports:
                    for name in named_imports.split(","):
                        name = name.strip().split(" as ")[0].strip()
                        if name:
                            result.references.append(ReferenceInfo(
                                from_entity=name,
                                to_entity=module_name,
                                kind="import"
                            ))
                if default_import:
                    result.references.append(ReferenceInfo(
                        from_entity=default_import,
                        to_entity=module_name,
                        kind="import"
                    ))

            match = require_pattern.search(line)
            if match:
                var_name = match.group(1)
                module_name = match.group(2).split("/")[-1].split(".")[0]
                result.references.append(ReferenceInfo(
                    from_entity=var_name,
                    to_entity=module_name,
                    kind="import"
                ))

    def _extract_calls(self, source_code: str, result: ParseResult):
        """提取函数调用关系
        BUG-JS-01修复：只在函数体范围内查找调用，而非全局匹配
        """
        lines = source_code.split('\n')
        func_names = {f.name for f in result.functions}
        call_pattern = re.compile(r'(\w+)\s*\(')
        skip_words = {"if", "for", "while", "switch", "catch", "return",
                      "new", "class", "function", "super", "this", "else",
                      "try", "throw", "typeof", "instanceof", "const", "let",
                      "var", "import", "export", "default", "from", "async",
                      "await", "yield", "delete", "void", "in", "of"}

        call_set = set()
        for func_info in result.functions:
            caller = func_info.name
            # 只在该函数的行号范围内查找调用
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
