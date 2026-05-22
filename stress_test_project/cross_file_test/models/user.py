"""用户数据模型"""
from dataclasses import dataclass
from typing import List, Optional
from utils.validators import validate_email, validate_phone

@dataclass
class User:
    name: str
    email: str
    phone: Optional[str] = None
    
    def validate(self):
        validate_email(self.email)
        if self.phone:
            validate_phone(self.phone)
    
    def to_dict(self):
        return {"name": self.name, "email": self.email}

@dataclass  
class Admin(User):
    role: str = "admin"
    
    def get_permissions(self):
        return ["read", "write", "delete"]
