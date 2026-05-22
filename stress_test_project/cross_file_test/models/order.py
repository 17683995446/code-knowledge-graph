"""订单数据模型"""
from dataclasses import dataclass
from typing import Optional
from models.user import User

@dataclass
class Order:
    id: int
    customer: User
    total: float
    
    def calculate_tax(self):
        return self.total * 0.1
    
    def get_customer_name(self):
        return self.customer.name
