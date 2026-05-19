"""
Debounce Queue - 防抖合并队列
将短时间内的多次文件变更事件合并为一次处理
"""

import asyncio
import time
from collections import defaultdict
from typing import Callable, Dict, Set, Optional


class DebounceQueue:
    """
    防抖队列：将窗口期内的多次文件变更合并为一次批量处理
    基于第一性原理：99%的代码修改只涉及1-2个文件
    """

    def __init__(self, debounce_window: float = 1.0,
                 callback: Optional[Callable] = None):
        self.debounce_window = debounce_window
        self.callback = callback
        self.pending_events: Dict[str, Set[str]] = defaultdict(set)
        self.lock = asyncio.Lock()
        self.timer_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def enqueue(self, file_path: str, event_type: str):
        """将文件变更事件加入队列"""
        async with self.lock:
            self.pending_events[file_path].add(event_type)
            if not self.is_running:
                self.is_running = True
                self.timer_task = asyncio.create_task(self._debounce_timer())

    async def _debounce_timer(self):
        """防抖定时器，窗口期结束后触发批量处理"""
        await asyncio.sleep(self.debounce_window)
        async with self.lock:
            if self.pending_events:
                batch = dict(self.pending_events)
                self.pending_events.clear()
                self.is_running = False
                if self.callback:
                    await self.callback(batch)

    async def flush(self):
        """立即处理所有待处理事件"""
        async with self.lock:
            if self.pending_events:
                batch = dict(self.pending_events)
                self.pending_events.clear()
                self.is_running = False
                if self.timer_task and not self.timer_task.done():
                    self.timer_task.cancel()
                if self.callback:
                    await self.callback(batch)

    def get_pending_count(self) -> int:
        """获取待处理事件数量"""
        return len(self.pending_events)
