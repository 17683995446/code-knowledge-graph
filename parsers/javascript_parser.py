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

    def parse_file(self, file_path: str) -> ParseResult:
        """解析JavaScript/TypeScript文件"""
        result = ParseResult()
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                source_code = fh.read()
            if not source_code.strip():
                return result

            lines = source_code.split("\n")
            self._extract_classes(lines, result)
            self._extract_functions(lines, result)
            self._extract_arrow_functions(lines, result)
            self._extract_imports(lines, result)
            self._extract_calls(source_code, result)
        except Exception:
            pass
        return result

    def _extract_classes(self, lines: List[str], result: ParseResult):
        """提取类定义和类方法"""
        pattern = re.compile(
            r'(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)'
            r'(?:\s+extends\s+(\w+))?'
            r'(?:\s+implements\s+([\w,\s]+))?'
        )
        
        current_class = ""
        brace_depth = 0
        in_class = False
        
        for line_num, line in enumerate(lines, 1):
            # 检测类定义
            match = pattern.search(line)
            if match:
                class_name = match.group(1)
                current_class = class_name
                in_class = True
                brace_depth = line.count('{') - line.count('}')
                
                result.types.append(TypeInfo(
                    name=class_name,
                    kind="class",
                    start_line=line_num,
                    end_line=line_num
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
                brace_depth += line.count('{') - line.count('}')
                if brace_depth <= 0:
                    in_class = False
                    current_class = ""
                    continue
                
                # 提取类方法
                method_pattern = re.compile(
                    r'^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{?'
                )
                method_match = method_pattern.match(line)
                if method_match:
                    method_name = method_match.group(1)
                    # 过滤关键字
                    skip_words = {"if", "for", "while", "switch", "catch", "return", 
                                 "new", "class", "function", "constructor", "super",
                                 "this", "else", "try", "throw", "typeof", "instanceof"}
                    if method_name not in skip_words and not method_name.startswith('//'):
                        result.functions.append(FunctionInfo(
                            name=method_name,
                            type_name=current_class,
                            start_line=line_num,
                            end_line=line_num
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
                result.functions.append(FunctionInfo(
                    name=func_name,
                    type_name="__module__",
                    start_line=line_num,
                    end_line=line_num
                ))

    def _extract_arrow_functions(self, lines: List[str], result: ParseResult):
        """提取箭头函数和const函数"""
        pattern = re.compile(
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?'
            r'(?:\([^)]*\)|\w+)\s*=>'
        )
        for line_num, line in enumerate(lines, 1):
            match = pattern.search(line)
            if match:
                func_name = match.group(1)
                result.functions.append(FunctionInfo(
                    name=func_name,
                    type_name="__module__",
                    start_line=line_num,
                    end_line=line_num
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
            end = func_info.end_line or start + 50
            search_text = '\n'.join(lines[max(0, start - 1):min(len(lines), end)])
            matches = call_pattern.findall(search_text)
            for callee in matches:
                if callee in func_names and callee != caller and callee not in skip_words:
                    call_set.add((caller, callee))

        for caller, callee in call_set:
            result.calls.append(CallInfo(caller=caller, callee=callee))
