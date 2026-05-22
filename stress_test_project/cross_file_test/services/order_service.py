"""订单服务"""
from models.order import Order
from services.user_service import UserService
from utils.logger import log, log_error

class OrderService:
    def __init__(self, user_service):
        self.user_service = user_service
        self.orders = []
        log("OrderService initialized")
    
    def create_order(self, customer_name, total):
        customer = self.user_service.find_by_name(customer_name)
        if not customer:
            log_error(f"Customer not found: {customer_name}")
            return None
        order = Order(id=len(self.orders)+1, customer=customer, total=total)
        self.orders.append(order)
        tax = order.calculate_tax()
        log(f"Order created: #{order.id}, tax={tax}")
        return order
    
    def get_total_revenue(self):
        return sum(o.total for o in self.orders)
    
    def get_customer_orders(self, customer_name):
        return [o for o in self.orders if o.customer.name == customer_name]
