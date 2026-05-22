"""
SiliconFlow Client - 硅基流动LLM客户端
使用硅基流动免费模型进行代码智能分析
"""

import asyncio
import random
import httpx
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """
    API限流异常
    BUG-LLM-05修复：用于处理429状态码
    """
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class SiliconFlowClient:
    """
    硅基流动LLM客户端
    调用硅基流动API进行代码知识图谱的智能分析
    """

    API_BASE_URL = "https://api.siliconflow.cn/v1/chat/completions"

    # BUG-LLM-02修复：可配置的默认超时时间
    DEFAULT_TIMEOUT = 30.0

    def __init__(self, api_key: str, model: str = "deepseek-ai/DeepSeek-V2.5",
                 timeout: Optional[float] = None):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def analyze_code_structure(self, stats: Dict[str, Any],
                                     graph_summary: Dict[str, Any]) -> Optional[str]:
        """分析代码结构并生成洞察"""
        prompt = self._build_structure_prompt(stats, graph_summary)
        return await self._chat_with_retry(prompt)

    async def analyze_file_relationships(self, dependency_data: Dict[str, Any]) -> Optional[str]:
        """分析文件间依赖关系"""
        prompt = self._build_dependency_prompt(dependency_data)
        return await self._chat_with_retry(prompt)

    async def generate_architecture_insight(self, project_info: Dict[str, Any]) -> Optional[str]:
        """生成架构洞察"""
        prompt = self._build_architecture_prompt(project_info)
        return await self._chat_with_retry(prompt)

    async def _chat_with_retry(self, prompt: str, max_tokens: int = 2000, max_retries: int = 3) -> Optional[str]:
        """
        带重试的聊天请求
        BUG-LLM-04修复：添加指数退避重试机制
        BUG-LLM-05修复：处理API限流(429状态码)
        """
        for attempt in range(max_retries):
            try:
                result = await self._chat(prompt, max_tokens)
                if result is not None:
                    return result
                # None结果可能是临时问题，重试
            except RateLimitError as e:
                # BUG-LLM-05修复：处理429限流，使用Retry-After头
                if attempt == max_retries - 1:
                    logger.error(f"API限流，已达最大重试次数: {e}")
                    raise
                wait_time = e.retry_after if e.retry_after else (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"API限流，等待 {wait_time:.1f} 秒后重试 (尝试 {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                # 指数退避
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"请求失败，等待 {wait_time:.1f} 秒后重试: {e}")
                await asyncio.sleep(wait_time)
        return None

    async def _chat(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """发送聊天请求到硅基流动API
        BUG-LLM-02修复：使用可配置的超时时间
        BUG-LLM-03修复：更完整的响应解析和错误处理
        """
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
            # BUG-LLM-02修复：使用实例配置的超时时间
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_BASE_URL,
                    headers=self.headers,
                    json=payload
                )
                if response.status_code == 200:
                    data = response.json()
                    # BUG-LLM-03修复：更完整的响应解析
                    return self._parse_response(data)
                elif response.status_code == 429:
                    # BUG-LLM-05修复：处理API限流(429状态码)
                    retry_after = None
                    retry_after_header = response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            retry_after = float(retry_after_header)
                        except ValueError:
                            pass
                    raise RateLimitError(f"API限流: {response.text}", retry_after)
                else:
                    logger.error(f"硅基流动API错误: {response.status_code} - {response.text}")
                    return None
        except httpx.TimeoutException:
            logger.error(f"硅基流动API请求超时(>{self.timeout}秒)")
            return None
        except httpx.ConnectError as e:
            logger.error(f"硅基流动API连接错误: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"硅基流动API响应JSON解析错误: {e}")
            return None
        except Exception as exception:
            logger.error(f"硅基流动API请求失败: {exception}")
            return None

    def _parse_response(self, data: Dict[str, Any]) -> Optional[str]:
        """解析API响应
        BUG-LLM-03修复：提取为独立方法，增加完整的响应解析
        """
        if not isinstance(data, dict):
            logger.warning(f"API响应不是字典类型: {type(data)}")
            return None

        # BUG-LLM-01修复：防御性检查API响应格式
        choices = data.get("choices", [])
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            logger.warning("API响应中没有choices或格式不正确")
            return None

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            logger.warning(f"第一个choice不是字典类型: {type(first_choice)}")
            return None

        message = first_choice.get("message", {})
        if not isinstance(message, dict):
            logger.warning(f"message不是字典类型: {type(message)}")
            return None

        content = message.get("content", "")
        if not content or not isinstance(content, str):
            logger.warning("API响应内容为空或格式不正确")
            return None

        # 清理内容
        content = content.strip()
        return content if content else None

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

主要文件: {[n.get('label', 'unknown') for n in nodes[:20]]}

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
