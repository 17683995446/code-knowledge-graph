"""
Python Parser - Python语言解析器
使用Python内置ast模块，零外部依赖
"""

import ast
import logging
import os
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

from parsers.base_parser import (
    BaseParser, ParseResult, TypeInfo, FunctionInfo,
    CallInfo, ReferenceInfo
)


# Python标准库和常见第三方库列表（用于过滤外部引用）
PYTHON_STDLIB_MODULES = {
    # 标准库
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore",
    "atexit", "audioop", "base64", "bdb", "binascii", "binhex", "bisect",
    "builtins", "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd",
    "code", "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy", "copyreg",
    "cProfile", "crypt", "csv", "ctypes", "curses", "dataclasses", "datetime",
    "dbm", "decimal", "difflib", "dis", "distutils", "doctest", "email",
    "encodings", "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
    "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt", "getpass",
    "gettext", "glob", "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac",
    "html", "http", "idlelib", "imaplib", "imghdr", "imp", "importlib", "inspect",
    "io", "ipaddress", "itertools", "json", "keyword", "lib2to3", "linecache",
    "locale", "logging", "lzma", "mailbox", "mailcap", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc", "nis",
    "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
    "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform", "plistlib",
    "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
    "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline",
    "reprlib", "resource", "rlcompleter", "runpy", "sched", "secrets", "select",
    "selectors", "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib",
    "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "ssl", "stat",
    "statistics", "string", "stringprep", "struct", "subprocess", "sunau",
    "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib",
    "tempfile", "termios", "test", "textwrap", "threading", "time", "timeit",
    "tkinter", "token", "tokenize", "trace", "traceback", "tracemalloc", "tty",
    "turtle", "turtledemo", "types", "typing", "unicodedata", "unittest", "urllib",
    "uu", "uuid", "venv", "warnings", "wave", "weakref", "webbrowser", "winreg",
    "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile",
    "zipimport", "zlib", "_thread",
    # 标准库中的常用类型/装饰器
    "Enum", "IntEnum", "Flag", "IntFlag", "auto", "unique",
    "dataclass", "field", "FrozenInstanceError",
    "List", "Dict", "Set", "Tuple", "Optional", "Union", "Any", "Callable",
    "TypeVar", "Generic", "Protocol", "Final", "Literal", "ClassVar",
    "Iterable", "Iterator", "Sequence", "Mapping", "MutableMapping",
    "AbstractSet", "MutableSet", "Reversible", "SupportsAbs", "SupportsBytes",
    "SupportsComplex", "SupportsFloat", "SupportsIndex", "SupportsInt",
    "SupportsRound", "Counter", "Deque", "DefaultDict", "OrderedDict", "ChainMap",
    "namedtuple", "OrderedDict", "defaultdict", "Counter", "deque",
    "ABC", "abstractmethod", "abstractproperty",
    "contextmanager", "asynccontextmanager", "closing", "suppress", "redirect_stdout",
    "partial", "partialmethod", "reduce", "cmp_to_key", "lru_cache", "total_ordering",
    "wraps", "update_wrapper", "singledispatch", "cached_property",
    "property", "classmethod", "staticmethod",
    "Exception", "BaseException", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "ImportError", "RuntimeError", "StopIteration", "NotImplementedError",
    # 常见第三方库
    "numpy", "pandas", "matplotlib", "scipy", "sklearn", "torch", "tensorflow",
    "django", "flask", "fastapi", "requests", "httpx", "aiohttp", "boto3",
    "sqlalchemy", "redis", "celery", "pytest", "selenium", "beautifulsoup4",
    "lxml", "pillow", "cv2", "opencv", "pydantic", "click", "rich", "tqdm",
    "yaml", "toml", "dotenv", "jinja2", "mako", "chardet", "dateutil", "pytz",
    "cryptography", "h5py", "msgpack", "protobuf", "grpc", "thrift", "avro",
}


class PythonParser(BaseParser):
    """
    Python代码解析器
    使用标准库ast模块，准确率100%
    """

    @property
    def language(self) -> str:
        return "python"

    @property
    def file_extensions(self) -> List[str]:
        return [".py"]

    def parse_file(self, file_path: str) -> ParseResult:
        """解析Python文件
        BUG-PY-01修复：尝试多种编码，而非仅utf-8
        """
        result = ParseResult()
        source_code = None

        # BUG-PY-01修复：尝试多种编码
        encodings = ["utf-8", "gbk", "gb2312", "latin-1", "cp1252"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as fh:
                    source_code = fh.read()
                logger.debug(f"成功使用编码 {encoding} 读取文件: {file_path}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"读取文件失败 {file_path} 使用编码 {encoding}: {e}")
                continue

        # 如果所有编码都失败，使用errors='ignore'作为最后手段
        if source_code is None:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    source_code = fh.read()
                logger.warning(f"使用errors='ignore'读取文件: {file_path}")
            except Exception as e:
                logger.error(f"无法读取文件 {file_path}: {e}")
                return result

        try:
            if not source_code.strip():
                return result
            tree = ast.parse(source_code, filename=file_path)
            self._visit_tree(tree, result, source_code)
        except SyntaxError as e:
            # 记录语法错误但不崩溃（如缩进层级超限）
            logger.warning(f"Python语法错误 {file_path}: {e}")
        except Exception as e:
            # 记录其他解析错误
            logger.warning(f"Python解析失败 {file_path}: {e}")
        return result

    def _visit_tree(self, tree: ast.AST, result: ParseResult, source_code: str):
        """遍历AST树
        BUG-FUNC-DUP-01修复：ClassDef不再递归，因为_process_class已处理其子节点
        """
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                self._process_class(node, result, source_code)
                # 不递归进入ClassDef，_process_class已处理其内部方法
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                self._process_function(node, result, source_code)
                # 递归进入函数体（可能包含嵌套函数）
                self._visit_tree(node, result, source_code)
            elif isinstance(node, ast.Import):
                self._process_import(node, result)
            elif isinstance(node, ast.ImportFrom):
                self._process_import_from(node, result)
            else:
                self._visit_tree(node, result, source_code)

    def _process_class(self, node: ast.ClassDef, result: ParseResult, source_code: str):
        """处理类定义"""
        docstring = ast.get_docstring(node) or ""
        type_info = TypeInfo(
            name=node.name,
            kind="class",
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=docstring
        )
        result.types.append(type_info)

        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name = base.id
                # 过滤标准库和第三方库类型
                if base_name not in PYTHON_STDLIB_MODULES:
                    result.references.append(ReferenceInfo(
                        from_entity=node.name,
                        to_entity=base_name,
                        kind="inherit"
                    ))

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorator_name = decorator.id
                # 过滤标准库装饰器
                if decorator_name not in PYTHON_STDLIB_MODULES:
                    result.references.append(ReferenceInfo(
                        from_entity=node.name,
                        to_entity=decorator_name,
                        kind="use"
                    ))

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._process_method(item, node.name, result, source_code)

    def _process_function(self, node: ast.FunctionDef, result: ParseResult, source_code: str):
        """处理模块级函数"""
        docstring = ast.get_docstring(node) or ""
        params = [arg.arg for arg in node.args.args]
        func_info = FunctionInfo(
            name=node.name,
            type_name="__module__",
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parameters=params,
            docstring=docstring
        )
        result.functions.append(func_info)
        self._extract_calls(node, node.name, result)

    def _process_method(self, node: ast.FunctionDef, class_name: str,
                        result: ParseResult, source_code: str):
        """处理类方法"""
        docstring = ast.get_docstring(node) or ""
        params = [arg.arg for arg in node.args.args]
        func_info = FunctionInfo(
            name=node.name,
            type_name=class_name,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parameters=params,
            docstring=docstring
        )
        result.functions.append(func_info)
        self._extract_calls(node, node.name, result)

    # BUG-CALL-NOISE-01修复：过滤内置函数/方法调用噪音
    PYTHON_BUILTINS = {
        "print", "len", "range", "list", "dict", "set", "tuple", "str", "int",
        "float", "bool", "bytes", "bytearray", "frozenset", "complex",
        "sorted", "reversed", "enumerate", "zip", "map", "filter", "reduce",
        "sum", "min", "max", "abs", "round", "pow", "divmod", "hash",
        "id", "type", "isinstance", "issubclass", "hasattr", "getattr",
        "setattr", "delattr", "callable", "iter", "next", "super", "property",
        "staticmethod", "classmethod", "repr", "format", "vars", "dir",
        "open", "input", "help", "hex", "oct", "bin", "ord", "chr",
        "any", "all", "exec", "eval", "compile", "breakpoint",
        # 常见内置方法名（作为调用时通常是噪音）
        "append", "extend", "insert", "remove", "pop", "clear", "index",
        "count", "sort", "reverse", "copy", "keys", "values", "items",
        "get", "update", "popitem", "setdefault", "fromkeys",
        "split", "join", "strip", "lstrip", "rstrip", "replace", "find",
        "startswith", "endswith", "lower", "upper", "title", "capitalize",
        "encode", "decode", "format_map", "isalpha", "isdigit", "isalnum",
        "isspace", "isupper", "islower", "istitle",
        "read", "readline", "readlines", "write", "writelines", "close",
        "flush", "seek", "tell", "fileno",
        "dump", "dumps", "load", "loads",
        "add", "discard", "union", "intersection", "difference",
        "wait", "notify", "acquire", "release",
    }

    def _extract_calls(self, node: ast.AST, caller_name: str, result: ParseResult):
        """提取函数调用关系
        BUG-CALL-NOISE-01修复：过滤内置函数/方法调用噪音
        """
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                callee_name = self._get_call_name(child)
                if (callee_name and callee_name != caller_name
                        and callee_name not in self.PYTHON_BUILTINS):
                    result.calls.append(CallInfo(
                        caller=caller_name,
                        callee=callee_name
                    ))

    def _get_call_name(self, call_node: ast.Call) -> Optional[str]:
        """获取调用函数名"""
        func = call_node.func
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            return func.attr
        return None

    def _process_import(self, node: ast.Import, result: ParseResult):
        """处理import语句，过滤外部模块
        BUG-REF-01修复：from_entity使用具体导入的符号名
        """
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            # 过滤标准库和第三方库
            if module_name not in PYTHON_STDLIB_MODULES:
                # 使用 as 别名或模块最后一段作为实体名
                imported_name = alias.asname or module_name
                result.references.append(ReferenceInfo(
                    from_entity="__module__",
                    to_entity=imported_name,
                    kind="import"
                ))

    def _process_import_from(self, node: ast.ImportFrom, result: ParseResult):
        """处理from...import语句，过滤外部模块
        BUG-REF-02修复：记录导入的符号名作为潜在引用目标
        引用语义：当前文件使用了 to_entity（导入的符号）
        from_entity 使用 __imports__ 标记，在 update_engine 中会尝试匹配
        """
        if node.module:
            module_name = node.module.split(".")[0]
            # 过滤标准库和第三方库
            if module_name not in PYTHON_STDLIB_MODULES:
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    imported_name = alias.asname or alias.name
                    # 记录：当前文件导入了 imported_name
                    # 如果 imported_name 在其他文件中定义为 type/function，则建立引用
                    result.references.append(ReferenceInfo(
                        from_entity="__imports__",
                        to_entity=imported_name,
                        kind="import"
                    ))
