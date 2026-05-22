#!/usr/bin/env python3
"""
Code Knowledge Graph System - 主启动入口
全编程语言代码知识图谱系统 - 基于第一性原理设计

用法:
    python main.py [项目路径] [--port PORT] [--db DB_PATH] [--api-key KEY]
"""

import os
import sys
import signal
import click
import logging
import asyncio
from pathlib import Path

# 将项目根目录加入Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from web.server import create_app
import uvicorn


# BUG-MAIN-01修复: 全局变量用于优雅关闭
_shutdown_event = None
_update_engine = None


def setup_logging(verbose: bool = False):
    """配置日志系统"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def signal_handler(signum, frame):
    """BUG-MAIN-01修复: 信号处理器，支持优雅关闭"""
    logger = logging.getLogger("main")
    logger.info(f"收到信号 {signum}，正在优雅关闭...")
    
    # 停止更新引擎
    global _update_engine
    if _update_engine:
        try:
            _update_engine.stop()
            logger.info("更新引擎已停止")
        except Exception as e:
            logger.error(f"停止更新引擎失败: {e}")
    
    # 设置关闭事件
    global _shutdown_event
    if _shutdown_event:
        _shutdown_event.set()
    
    # 强制退出（作为最后手段）
    import threading
    def force_exit():
        import time
        time.sleep(5)  # 等待5秒让优雅关闭完成
        logger.warning("优雅关闭超时，强制退出")
        os._exit(0)
    
    exit_thread = threading.Thread(target=force_exit, daemon=True)
    exit_thread.start()


@click.command()
@click.argument("project_path", default=".")
@click.option("--port", default=8000, help="Web服务端口", type=int)
@click.option("--host", default="0.0.0.0", help="Web服务地址")
@click.option("--db", default="code_knowledge.db", help="SQLite数据库路径")
@click.option("--api-key", default="", help="硅基流动API密钥")
@click.option("--verbose", is_flag=True, help="启用详细日志")
def main(project_path: str, port: int, host: str, db: str, api_key: str, verbose: bool):
    """
    代码知识图谱系统 - 全编程语言代码知识图谱构建与可视化

    PROJECT_PATH: 要分析的项目路径（默认当前目录）
    """
    setup_logging(verbose)
    logger = logging.getLogger("main")

    # BUG-MAIN-01修复: 注册信号处理器
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("已注册信号处理器 (SIGINT, SIGTERM)")

    project_path = os.path.abspath(project_path)
    if not os.path.isdir(project_path):
        logger.error(f"项目路径不存在: {project_path}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("  代码知识图谱系统 v1.0.0")
    logger.info("  Code Knowledge Graph System")
    logger.info("=" * 60)
    logger.info(f"  项目路径: {project_path}")
    logger.info(f"  数据库:   {db}")
    logger.info(f"  服务地址: http://{host}:{port}")
    logger.info(f"  LLM集成:  {'已启用' if api_key else '未配置'}")
    logger.info("=" * 60)

    app = create_app(
        project_path=project_path,
        database_path=db,
        host=host,
        port=port,
        siliconflow_api_key=api_key
    )

    # BUG-MAIN-01修复: 获取update_engine引用用于优雅关闭
    global _update_engine
    # 尝试从app.state获取update_engine
    try:
        from web.server import get_update_engine
        _update_engine = get_update_engine()
    except Exception:
        pass  # 如果获取失败，优雅关闭时跳过

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info" if not verbose else "debug",
            ws_ping_interval=30,
            ws_ping_timeout=10
        )
    except KeyboardInterrupt:
        logger.info("收到键盘中断，正在关闭...")
    finally:
        # BUG-MAIN-01修复: 确保清理资源
        if _update_engine:
            try:
                _update_engine.stop()
            except Exception:
                pass
        logger.info("系统已关闭")


if __name__ == "__main__":
    main()
