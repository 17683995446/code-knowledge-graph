"""
Parsers Package - 多语言解析器模块
可插拔式语言解析器，所有解析器实现统一接口
"""

from parsers.base_parser import BaseParser, ParseResult, TypeInfo, FunctionInfo, CallInfo, ReferenceInfo
from parsers.python_parser import PythonParser
from parsers.javascript_parser import JavaScriptParser
from parsers.java_parser import JavaParser
from parsers.go_parser import GoParser
from parsers.parser_registry import ParserRegistry

__all__ = [
    "BaseParser", "ParseResult", "TypeInfo", "FunctionInfo", "CallInfo", "ReferenceInfo",
    "PythonParser", "JavaScriptParser", "JavaParser", "GoParser", "ParserRegistry"
]
