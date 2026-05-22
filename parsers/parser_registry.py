"""
Parser Registry - 解析器注册中心
管理所有语言解析器的注册和查找
"""

import logging
from typing import Dict, List, Optional
from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


class ParserRegistryError(Exception):
    """解析器注册中心异常"""
    pass


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
        """
        创建包含所有内置解析器的默认注册中心
        BUG-REG-02修复：记录警告日志，如果全部失败抛出异常
        """
        failed_parsers = []
        
        try:
            from parsers.python_parser import PythonParser
            self.register(PythonParser())
        except ImportError as e:
            logger.warning(f"Python解析器加载失败: {e}")
            failed_parsers.append("Python")

        try:
            from parsers.javascript_parser import JavaScriptParser
            self.register(JavaScriptParser())
        except ImportError as e:
            logger.warning(f"JavaScript解析器加载失败: {e}")
            failed_parsers.append("JavaScript")

        try:
            from parsers.java_parser import JavaParser
            self.register(JavaParser())
        except ImportError as e:
            logger.warning(f"Java解析器加载失败: {e}")
            failed_parsers.append("Java")

        try:
            from parsers.go_parser import GoParser
            self.register(GoParser())
        except ImportError as e:
            logger.warning(f"Go解析器加载失败: {e}")
            failed_parsers.append("Go")

        # BUG-REG-02修复：如果所有解析器都加载失败，抛出异常
        if len(self.parsers) == 0:
            error_msg = f"所有解析器加载失败: {', '.join(failed_parsers)}"
            logger.error(error_msg)
            raise ParserRegistryError(error_msg)
        
        if failed_parsers:
            logger.warning(f"部分解析器加载失败: {', '.join(failed_parsers)}，已加载: {list(self.parsers.keys())}")
        else:
            logger.info(f"所有解析器加载成功: {list(self.parsers.keys())}")

        return self
