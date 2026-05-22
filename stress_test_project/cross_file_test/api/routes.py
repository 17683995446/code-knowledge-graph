"""API路由"""
from services.user_service import UserService
from services.order_service import OrderService
from utils.logger import log

user_service = UserService()
order_service = OrderService(user_service)

def handle_create_user(name, email):
    return user_service.create_user(name, email)

def handle_create_order(customer_name, total):
    return order_service.create_order(customer_name, total)

def handle_get_revenue():
    revenue = order_service.get_total_revenue()
    log(f"Revenue query: {revenue}")
    return revenue
