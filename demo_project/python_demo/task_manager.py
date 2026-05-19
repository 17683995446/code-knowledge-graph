"""
Demo Application - 演示应用模块
包含多语言示例代码，展示知识图谱系统的解析能力
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskItem:
    """任务项数据类"""
    task_id: int
    title: str
    description: str
    status: TaskStatus
    priority: int = 0

    def mark_completed(self):
        """标记任务为已完成"""
        self.status = TaskStatus.COMPLETED

    def is_high_priority(self) -> bool:
        """判断是否为高优先级"""
        return self.priority >= 80


class TaskManager:
    """任务管理器"""

    def __init__(self):
        self.tasks: List[TaskItem] = []

    def add_task(self, title: str, description: str, priority: int = 0) -> TaskItem:
        """添加新任务"""
        task = TaskItem(
            task_id=len(self.tasks) + 1,
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            priority=priority
        )
        self.tasks.append(task)
        return task

    def get_pending_tasks(self) -> List[TaskItem]:
        """获取待处理任务"""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def complete_task(self, task_id: int) -> Optional[TaskItem]:
        """完成任务"""
        for task in self.tasks:
            if task.task_id == task_id:
                task.mark_completed()
                return task
        return None

    def get_statistics(self) -> dict:
        """获取任务统计"""
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        return {
            "total_tasks": total,
            "completed_tasks": completed,
            "completion_rate": completed / total if total > 0 else 0
        }


class ReportGenerator:
    """报告生成器"""

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager

    def generate_summary(self) -> str:
        """生成任务摘要报告"""
        stats = self.task_manager.get_statistics()
        summary = f"任务摘要报告\n"
        summary += f"总任务数: {stats['total_tasks']}\n"
        summary += f"已完成: {stats['completed_tasks']}\n"
        summary += f"完成率: {stats['completion_rate']:.1%}\n"
        return summary

    def export_to_json(self) -> dict:
        """导出为JSON格式"""
        return {
            "tasks": [
                {
                    "id": t.task_id,
                    "title": t.title,
                    "status": t.status.value
                }
                for t in self.task_manager.tasks
            ]
        }


def main():
    """主函数"""
    manager = TaskManager()
    manager.add_task("设计数据库", "设计知识图谱数据库表结构", priority=90)
    manager.add_task("实现解析器", "实现Python代码解析器", priority=85)
    manager.add_task("构建Web服务", "搭建FastAPI可视化服务", priority=80)

    generator = ReportGenerator(manager)
    print(generator.generate_summary())


if __name__ == "__main__":
    main()
