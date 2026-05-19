"""
Parser Registry - 解析器注册中心
管理所有语言解析器的注册和查找
"""

from typing import Dict, List, Optional
from parsers.base_parser import BaseParser


class ParserRegistry:
    """
    解析器注册中心
    基于第一性原理：可插拔解析器，不同语言只需实现解析器接口
    """

    def __init__(self):
        self.parsers: Dict[str, BaseParser] = {}

    def register(self, parser: BaseParser):
        """注册解析器"""
        self.parsers[parser.language] = parser

    def get_parser(self, language: str) -> Optional[BaseParser]:
        """根据语言获取解析器"""
        return self.parsers.get(language)

    def get_supported_languages(self) -> List[str]:
        """获取所有支持的语言列表"""
        return list(self.parsers.keys())

    def create_default_registry(self) -> "ParserRegistry":
        """创建包含所有内置解析器的默认注册中心"""
        try:
            from parsers.python_parser import PythonParser
            self.register(PythonParser())
        except ImportError:
            pass

        try:
            from parsers.javascript_parser import JavaScriptParser
            self.register(JavaScriptParser())
        except ImportError:
            pass

        try:
            from parsers.java_parser import JavaParser
            self.register(JavaParser())
        except ImportError:
            pass

        try:
            from parsers.go_parser import GoParser
            self.register(GoParser())
        except ImportError:
            pass

        return self
