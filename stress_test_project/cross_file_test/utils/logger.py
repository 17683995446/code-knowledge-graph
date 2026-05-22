"""日志工具"""
import datetime

_log_level = "INFO"

def set_log_level(level):
    global _log_level
    _log_level = level

def log(message, level="INFO"):
    timestamp = datetime.datetime.now().isoformat()
    print(f"[{timestamp}] [{level}] {message}")

def log_error(message):
    log(message, "ERROR")
