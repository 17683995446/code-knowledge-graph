"""
Base Parser - 通用解析器接口
所有语言解析器必须实现此接口
基于第一性原理：所有语言共享同一套解析结果格式
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


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

    @staticmethod
    def compute_end_line(lines: list, start_line: int,
                          comment_single: str = "//",
                          comment_multi_start: str = "/*",
                          comment_multi_end: str = "*/") -> int:
        """通过花括号深度追踪计算函数/方法的结束行号
        BUG-CALL-ALL-01修复：正确计算end_line使_extract_calls能覆盖方法体
        BUG-STR-LIT-01修复：感知字符串和注释，避免误匹配
        BUG-BP-006修复：每行开始时重置单行注释状态
        BUG-BP-002修复：扫描范围扩大到2000行
        BUG-BP-004修复：转义字符j+=2添加边界检查
        BUG-BP-005修复：增加反引号字符串支持
        """
        depth = 0
        found_first_brace = False
        in_string = None  # None, '"', "'", '`'
        in_comment = None

        for i in range(start_line - 1, min(len(lines), start_line + 2000)):
            line = lines[i]
            # BUG-BP-006修复：每行开始时重置单行注释状态
            # 单行注释不会跨行，新行开始时必须清除
            if in_comment == comment_single:
                in_comment = None
            j = 0
            while j < len(line):
                ch = line[j]

                # 处理注释结束
                if in_comment == comment_single and ch == '\n':
                    in_comment = None
                    j += 1
                    continue
                if (in_comment == comment_multi_start and
                        j + len(comment_multi_end) - 1 < len(line) and
                        line[j:j + len(comment_multi_end)] == comment_multi_end):
                    in_comment = None
                    j += len(comment_multi_end)
                    continue

                if in_comment:
                    j += 1
                    continue

                # 处理字符串（支持转义）
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
                    # BUG-BP-005修复：增加反引号支持
                    in_string = ch
                    j += 1
                    continue
                # 在字符串中但不是转义/关闭时，跳过后续处理
                if in_string:
                    j += 1
                    continue

                # 处理注释 — 只在不在字符串中时检测
                if in_comment is None and j + 1 < len(line):
                    two = line[j:j + 2]
                    if two == comment_single:
                        in_comment = comment_single
                        break  # 单行注释，跳过本行剩余部分
                    if two == comment_multi_start:
                        in_comment = comment_multi_start
                        j += 2
                        continue

                # 计算花括号深度
                if ch == '{':
                    depth += 1
                    found_first_brace = True
                elif ch == '}':
                    depth -= 1
                    if found_first_brace and depth <= 0:
                        return i + 1
                j += 1

        # BUG-BP-007修复：花括号匹配失败时记录警告
        if found_first_brace:
            logger.debug(f"compute_end_line: 未找到匹配的闭合花括号, start_line={start_line}")
        return start_line
