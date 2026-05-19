#!/usr/bin/env python3
"""
Code Knowledge Graph System - 主启动入口
全编程语言代码知识图谱系统 - 基于第一性原理设计

用法:
    python main.py [项目路径] [--port PORT] [--db DB_PATH] [--api-key KEY]
"""

import os
import sys
import click
import logging
from pathlib import Path

# 将项目根目录加入Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from web.server import create_app
import uvicorn


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

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info" if not verbose else "debug",
        ws_ping_interval=30,
        ws_ping_timeout=10
    )


if __name__ == "__main__":
    main()
