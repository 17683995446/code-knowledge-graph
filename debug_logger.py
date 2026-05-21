"""
Debug Logger - 调试日志增强模块
为代码知识图谱系统提供详细的执行日志跟踪
"""

import logging
import functools
import inspect
import time
from typing import Any, Callable

# 创建详细的日志格式
DETAILED_FORMAT = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S.%f'
)

# 简化格式
SIMPLE_FORMAT = logging.Formatter(
    '[%(levelname)s] %(name)s: %(message)s'
)


def setup_debug_logging(level=logging.DEBUG):
    """设置调试级别的日志记录"""
    # 清除现有处理器
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.setLevel(level)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(DETAILED_FORMAT)
    root_logger.addHandler(console_handler)

    # 文件处理器
    file_handler = logging.FileHandler('code_knowledge_debug.log', mode='w')
    file_handler.setLevel(level)
    file_handler.setFormatter(DETAILED_FORMAT)
    root_logger.addHandler(file_handler)

    logging.info("=" * 80)
    logging.info("调试日志系统已启动")
    logging.info("=" * 80)


def log_entry_exit(func: Callable) -> Callable:
    """装饰器：记录函数入口和出口"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = func.__qualname__

        # 记录入口
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        # 简化参数显示
        args_str = ", ".join([
            f"{k}=..." if isinstance(v, (str, bytes)) and len(str(v)) > 50 else f"{k}={repr(v)}"
            for k, v in bound.arguments.items()
        ])
        logger.debug(f"[ENTRY] {func_name}({args_str})")

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"[EXIT] {func_name} -> 成功 (耗时: {elapsed:.3f}s)")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[EXIT] {func_name} -> 异常: {e} (耗时: {elapsed:.3f}s)")
            raise

    return wrapper


def log_line_execution(logger_name: str, line_desc: str):
    """记录代码行执行"""
    logger = logging.getLogger(logger_name)
    logger.debug(f"[LINE] {line_desc}")


class ExecutionTracer:
    """执行跟踪器 - 跟踪代码执行路径"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self.execution_path = []

    def trace(self, step: str, data: Any = None):
        """记录执行步骤"""
        self.execution_path.append(step)
        if data is not None:
            self.logger.debug(f"[TRACE] {self.name}: {step} | data={repr(data)[:100]}")
        else:
            self.logger.debug(f"[TRACE] {self.name}: {step}")

    def trace_branch(self, condition: str, result: bool):
        """记录分支判断"""
        self.logger.debug(f"[BRANCH] {self.name}: {condition} = {result}")

    def trace_loop(self, iteration: int, data: Any = None):
        """记录循环迭代"""
        if data is not None:
            self.logger.debug(f"[LOOP] {self.name}: 迭代 {iteration} | data={repr(data)[:100]}")
        else:
            self.logger.debug(f"[LOOP] {self.name}: 迭代 {iteration}")

    def trace_error(self, error: Exception, context: str = ""):
        """记录错误"""
        self.logger.error(f"[ERROR] {self.name}: {context} | {type(error).__name__}: {error}")

    def get_path(self) -> list:
        """获取执行路径"""
        return self.execution_path.copy()


# 全局跟踪器注册表
tracers = {}


def get_tracer(name: str) -> ExecutionTracer:
    """获取或创建跟踪器"""
    if name not in tracers:
        tracers[name] = ExecutionTracer(name)
    return tracers[name]


def log_variable_state(logger_name: str, var_name: str, var_value: Any):
    """记录变量状态"""
    logger = logging.getLogger(logger_name)
    value_str = repr(var_value)
    if len(value_str) > 200:
        value_str = value_str[:200] + "..."
    logger.debug(f"[VAR] {var_name} = {value_str}")


def log_checkpoint(logger_name: str, checkpoint_name: str):
    """记录检查点"""
    logger = logging.getLogger(logger_name)
    logger.info(f"[CHECKPOINT] {checkpoint_name}")


# 性能计时器
class PerformanceTimer:
    """性能计时器"""

    def __init__(self, name: str, logger_name: str = None):
        self.name = name
        self.logger = logging.getLogger(logger_name or __name__)
        self.start_time = None
        self.elapsed = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"[TIMER START] {self.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.time() - self.start_time
        if exc_type is None:
            self.logger.info(f"[TIMER END] {self.name}: {self.elapsed:.3f}s")
        else:
            self.logger.error(f"[TIMER END] {self.name}: {self.elapsed:.3f}s (发生异常: {exc_type.__name__})")


def trace_execution(func: Callable) -> Callable:
    """装饰器：详细跟踪函数执行"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tracer = get_tracer(func.__qualname__)
        logger = logging.getLogger(func.__module__)

        tracer.trace("开始执行")

        # 记录参数
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        for name, value in bound.arguments.items():
            log_variable_state(func.__module__, f"参数.{name}", value)

        try:
            with PerformanceTimer(func.__qualname__, func.__module__):
                result = func(*args, **kwargs)

            tracer.trace("执行成功")
            log_variable_state(func.__module__, "返回值", result)
            return result

        except Exception as e:
            tracer.trace_error(e, "函数执行")
            raise

    return wrapper