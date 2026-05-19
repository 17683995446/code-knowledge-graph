"""
Base Models - 基础模型定义
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class BaseEntity:
    """基础实体类"""
    entity_id: int
    entity_name: str
    is_active: bool = True

    def validate(self) -> bool:
        """验证实体"""
        return self.entity_id > 0 and len(self.entity_name) > 0


@dataclass
class AuditableEntity(BaseEntity):
    """可审计实体 - 继承自BaseEntity"""
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    def audit(self) -> dict:
        """生成审计记录"""
        return {
            "entity_id": self.entity_id,
            "created_by": self.created_by,
            "updated_by": self.updated_by
        }
