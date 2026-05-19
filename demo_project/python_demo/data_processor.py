"""
Data Processor - 数据处理模块
提供数据清洗、转换和聚合功能
"""

import json
from typing import Dict, List, Any, Callable
from collections import defaultdict


class DataPipeline:
    """数据处理管道"""

    def __init__(self):
        self.stages: List[Callable] = []
        self.data: List[Dict[str, Any]] = []

    def add_stage(self, processor: Callable) -> "DataPipeline":
        """添加处理阶段"""
        self.stages.append(processor)
        return self

    def load_data(self, records: List[Dict[str, Any]]) -> "DataPipeline":
        """加载数据"""
        self.data = list(records)
        return self

    def execute(self) -> List[Dict[str, Any]]:
        """执行所有处理阶段"""
        result = list(self.data)
        for stage in self.stages:
            result = stage(result)
        return result

    def get_result_count(self) -> int:
        """获取结果数量"""
        return len(self.data)


class DataAggregator:
    """数据聚合器"""

    @staticmethod
    def group_by_field(records: List[Dict], field_name: str) -> Dict[str, List[Dict]]:
        """按字段分组"""
        groups = defaultdict(list)
        for record in records:
            key = record.get(field_name, "unknown")
            groups[key].append(record)
        return dict(groups)

    @staticmethod
    def sum_field(records: List[Dict], field_name: str) -> float:
        """对数值字段求和"""
        return sum(r.get(field_name, 0) for r in records)

    @staticmethod
    def filter_records(records: List[Dict], condition: Callable) -> List[Dict]:
        """按条件过滤记录"""
        return [r for r in records if condition(r)]


class JsonDataExporter:
    """JSON数据导出器"""

    @staticmethod
    def export(records: List[Dict], output_path: str, indent: int = 2):
        """导出数据到JSON文件"""
        with open(output_path, "w", encoding="utf-8") as file_handle:
            json.dump(records, file_handle, ensure_ascii=False, indent=indent)

    @staticmethod
    def import_data(input_path: str) -> List[Dict]:
        """从JSON文件导入数据"""
        with open(input_path, "r", encoding="utf-8") as file_handle:
            return json.load(file_handle)


def create_default_pipeline() -> DataPipeline:
    """创建默认数据处理管道"""
    pipeline = DataPipeline()
    pipeline.add_stage(lambda data: [r for r in data if r.get("active", True)])
    pipeline.add_stage(lambda data: sorted(data, key=lambda x: x.get("priority", 0), reverse=True))
    return pipeline
