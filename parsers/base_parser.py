"""
Base Parser - 通用解析器接口
所有语言解析器必须实现此接口
基于第一性原理：所有语言共享同一套解析结果格式
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TypeInfo:
    """类型信息（class/interface/struct/enum等）"""
    name: str
    kind: str  # class/interface/struct/enum/protocol/module
    flags: int = 0
    start_line: int = 0
    end_line: int = 0
    docstring: str = ""


@dataclass
class FunctionInfo:
    """函数信息（方法/函数/过程等）"""
    name: str
    type_name: str = ""  # 所属类型名
    start_line: int = 0
    end_line: int = 0
    parameters: List[str] = field(default_factory=list)
    return_type: str = ""
    docstring: str = ""


@dataclass
class CallInfo:
    """调用关系"""
    caller: str  # 调用者名称
    callee: str  # 被调用者名称


@dataclass
class ReferenceInfo:
    """引用关系"""
    from_entity: str  # 源实体
    to_entity: str    # 目标实体
    kind: str         # inherit/implement/import/use


@dataclass
class ParseResult:
    """解析结果（所有语言统一格式）"""
    types: List[TypeInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    calls: List[CallInfo] = field(default_factory=list)
    references: List[ReferenceInfo] = field(default_factory=list)


class BaseParser(ABC):
    """
    通用解析器抽象基类
    所有语言解析器必须实现 parse_file 方法
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """返回解析器支持的语言名称"""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> List[str]:
        """返回支持的文件扩展名列表"""
        pass

    @abstractmethod
    def parse_file(self, file_path: str) -> ParseResult:
        """
        解析单个文件，返回统一的解析结果
        这是所有解析器的核心接口
        """
        pass

    def can_parse(self, file_path: str) -> bool:
        """检查是否能解析指定文件"""
        import os
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.file_extensions
