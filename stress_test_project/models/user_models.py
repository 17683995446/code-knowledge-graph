"""
User Models - 用户模型
"""

from dataclasses import dataclass
from typing import List, Optional
from models.base_models import BaseEntity, AuditableEntity


@dataclass
class User(AuditableEntity):
    """用户实体 - 继承自AuditableEntity"""
    email: str = ""
    role: str = "user"

    def get_display_name(self) -> str:
        """获取显示名称"""
        return f"{self.entity_name} ({self.email})"

    def is_admin(self) -> bool:
        """检查是否管理员"""
        return self.role == "admin"


@dataclass
class UserGroup(BaseEntity):
    """用户组实体"""
    members: List[User] = None

    def __post_init__(self):
        if self.members is None:
            self.members = []

    def add_member(self, user: User) -> None:
        """添加成员"""
        self.members.append(user)

    def get_member_count(self) -> int:
        """获取成员数量"""
        return len(self.members)


class UserRepository:
    """用户仓库"""

    def __init__(self):
        self._users: List[User] = []

    def add(self, user: User) -> None:
        """添加用户"""
        self._users.append(user)

    def find_by_id(self, entity_id: int) -> Optional[User]:
        """按ID查找"""
        for user in self._users:
            if user.entity_id == entity_id:
                return user
        return None

    def find_by_email(self, email: str) -> Optional[User]:
        """按邮箱查找"""
        for user in self._users:
            if user.email == email:
                return user
        return None
