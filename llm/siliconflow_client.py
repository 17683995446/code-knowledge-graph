"""
SiliconFlow Client - 硅基流动LLM客户端
使用硅基流动免费模型进行代码智能分析
"""

import httpx
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SiliconFlowClient:
    """
    硅基流动LLM客户端
    调用硅基流动API进行代码知识图谱的智能分析
    """

    API_BASE_URL = "https://api.siliconflow.cn/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "deepseek-ai/DeepSeek-V2.5"):
        self.api_key = api_key
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def analyze_code_structure(self, stats: Dict[str, Any],
                                     graph_summary: Dict[str, Any]) -> Optional[str]:
        """分析代码结构并生成洞察"""
        prompt = self._build_structure_prompt(stats, graph_summary)
        return await self._chat(prompt)

    async def analyze_file_relationships(self, dependency_data: Dict[str, Any]) -> Optional[str]:
        """分析文件间依赖关系"""
        prompt = self._build_dependency_prompt(dependency_data)
        return await self._chat(prompt)

    async def generate_architecture_insight(self, project_info: Dict[str, Any]) -> Optional[str]:
        """生成架构洞察"""
        prompt = self._build_architecture_prompt(project_info)
        return await self._chat(prompt)

    async def _chat(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """发送聊天请求到硅基流动API"""
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个代码架构分析专家。请用中文回答，简洁专业。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.API_BASE_URL,
                    headers=self.headers,
                    json=payload
                )
                if response.status_code == 200:
                    data = response.json()
                    # BUG-LLM-01 修复：防御性检查API响应格式
                    choices = data.get("choices", [])
                    if choices and isinstance(choices, list):
                        content = choices[0].get("message", {}).get("content", "")
                        return content if content else None
                    return None
                else:
                    logger.error(f"硅基流动API错误: {response.status_code} - {response.text}")
                    return None
        except Exception as exception:
            logger.error(f"硅基流动API请求失败: {exception}")
            return None

    def _build_structure_prompt(self, stats: Dict[str, Any],
                                graph_summary: Dict[str, Any]) -> str:
        """构建代码结构分析提示"""
        return f"""请分析以下代码项目的知识图谱统计数据，给出简洁的架构洞察：

项目统计：
- 文件总数: {stats.get('total_files', 0)}
- 类型总数: {stats.get('total_types', 0)}
- 函数总数: {stats.get('total_functions', 0)}
- 调用关系数: {stats.get('total_calls', 0)}
- 引用关系数: {stats.get('total_references', 0)}
- 语言分布: {json.dumps(stats.get('languages', {}), ensure_ascii=False)}
- 类型分布: {json.dumps(stats.get('type_kinds', {}), ensure_ascii=False)}

请从以下角度分析：
1. 项目规模和技术栈特征
2. 代码组织模式（面向对象/函数式/混合）
3. 模块耦合度评估
4. 改进建议（如有）

请控制在200字以内。"""

    def _build_dependency_prompt(self, dependency_data: Dict[str, Any]) -> str:
        """构建依赖分析提示"""
        nodes = dependency_data.get("nodes", [])
        edges = dependency_data.get("edges", [])
        edge_summary = {}
        for edge in edges[:50]:
            kind = edge.get("kind", "unknown")
            edge_summary[kind] = edge_summary.get(kind, 0) + 1

        return f"""请分析以下代码项目的文件依赖关系：

文件数: {len(nodes)}
依赖关系数: {len(edges)}
关系类型分布: {json.dumps(edge_summary, ensure_ascii=False)}

主要文件: {[n['label'] for n in nodes[:20]]}

请分析：
1. 依赖关系是否合理
2. 是否存在循环依赖风险
3. 模块化程度评估

请控制在150字以内。"""

    def _build_architecture_prompt(self, project_info: Dict[str, Any]) -> str:
        """构建架构洞察提示"""
        return f"""基于以下项目信息，生成简洁的架构描述：

{json.dumps(project_info, ensure_ascii=False, indent=2)}

请生成一段50字以内的架构概述。"""
