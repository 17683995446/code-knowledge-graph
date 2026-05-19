"""
Web Server - FastAPI Web服务
提供REST API和WebSocket实时推送，以及前端页面
"""

import os
import asyncio
import logging
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.database import KnowledgeDatabase
from core.update_engine import UpdateEngine
from core.file_watcher import FileWatcher
from parsers.parser_registry import ParserRegistry
from web.websocket_manager import WebSocketManager
from llm.siliconflow_client import SiliconFlowClient

logger = logging.getLogger(__name__)


def create_app(project_path: str, database_path: str = "code_knowledge.db",
               host: str = "0.0.0.0", port: int = 8000,
               siliconflow_api_key: str = "") -> FastAPI:
    """
    创建并配置FastAPI应用
    """
    app = FastAPI(
        title="代码知识图谱系统",
        description="全编程语言代码知识图谱 - 基于第一性原理设计",
        version="1.0.0"
    )

    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    database = KnowledgeDatabase(database_path)
    parser_registry = ParserRegistry().create_default_registry()
    websocket_manager = WebSocketManager()

    llm_client = None
    if siliconflow_api_key:
        llm_client = SiliconFlowClient(api_key=siliconflow_api_key)

    update_engine = UpdateEngine(
        project_path=project_path,
        database=database,
        parser_registry=parser_registry,
        debounce_window=1.0,
        on_update_callback=_make_update_callback(websocket_manager, database, llm_client)
    )

    app.state.database = database
    app.state.update_engine = update_engine
    app.state.websocket_manager = websocket_manager
    app.state.llm_client = llm_client
    app.state.project_path = project_path

    @app.on_event("startup")
    async def startup_event():
        logger.info(f"正在全量同步项目: {project_path}")
        # BUG-API-02修复：在线程池中执行全量同步，避免阻塞事件循环
        loop = asyncio.get_event_loop()
        sync_result = await loop.run_in_executor(None, update_engine.full_sync)
        logger.info(f"全量同步完成: {sync_result}")
        update_engine.start()
        asyncio.create_task(update_engine.start_async_loop())
        logger.info(f"文件监控已启动")
        logger.info(f"Web服务已启动: http://{host}:{port}")

    @app.on_event("shutdown")
    async def shutdown_event():
        update_engine.stop()
        database.close()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as fh:
                return HTMLResponse(content=fh.read())
        return HTMLResponse(content="<h1>代码知识图谱系统</h1><p>静态文件未找到</p>")

    @app.get("/api/statistics")
    async def get_statistics():
        stats = database.get_statistics()
        stats["project_path"] = project_path
        stats["supported_languages"] = parser_registry.get_supported_languages()
        stats["engine_stats"] = update_engine.stats
        return stats

    @app.get("/api/graph")
    async def get_graph_data():
        return database.get_graph_data()

    @app.get("/api/dependency-graph")
    async def get_dependency_graph():
        return database.get_dependency_graph()

    @app.get("/api/files")
    async def get_files():
        files = database.get_all_files()
        return [
            {
                "id": f.file_id,
                "path": f.file_path,
                "language": f.language,
                "modified": datetime.fromtimestamp(f.modified_time).isoformat()
            }
            for f in files
        ]

    @app.get("/api/file/{file_path:path}")
    async def get_file_details(file_path: str):
        details = database.get_file_details(file_path)
        if not details:
            raise HTTPException(status_code=404, detail="文件未找到")
        return details

    @app.get("/api/languages")
    async def get_languages():
        return {
            "supported": parser_registry.get_supported_languages(),
            "extensions": FileWatcher.get_language_extensions()
        }

    @app.post("/api/sync")
    async def trigger_sync():
        # BUG-API-01修复：在线程池中执行全量同步
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, update_engine.full_sync)
        await websocket_manager.broadcast({
            "type": "full_sync",
            "data": {"timestamp": datetime.now().isoformat(), **result}
        })
        return result

    @app.get("/api/analysis/structure")
    async def analyze_structure():
        if not llm_client:
            return JSONResponse(status_code=503, content={"error": "LLM未配置"})
        stats = database.get_statistics()
        graph_data = database.get_graph_data()
        analysis = await llm_client.analyze_code_structure(
            stats,
            {"nodes": len(graph_data["nodes"]), "edges": len(graph_data["edges"])}
        )
        if not analysis:
            return JSONResponse(status_code=502, content={"error": "LLM分析失败，请检查API密钥"})
        return {"analysis": analysis}

    @app.get("/api/analysis/dependencies")
    async def analyze_dependencies():
        if not llm_client:
            return JSONResponse(status_code=503, content={"error": "LLM未配置"})
        dep_graph = database.get_dependency_graph()
        analysis = await llm_client.analyze_file_relationships(dep_graph)
        if not analysis:
            return JSONResponse(status_code=502, content={"error": "LLM分析失败，请检查API密钥"})
        return {"analysis": analysis}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            websocket_manager.disconnect(websocket)

    return app


def _make_update_callback(websocket_manager: WebSocketManager,
                          database: KnowledgeDatabase,
                          llm_client: SiliconFlowClient):
    """创建更新回调函数"""
    async def on_update(updated_files: list, errors: list):
        await websocket_manager.send_update_notification(updated_files, errors)
        stats = database.get_statistics()
        await websocket_manager.send_stats_update(stats)
    return on_update
