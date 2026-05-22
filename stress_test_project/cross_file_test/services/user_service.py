"""用户服务"""
from models.user import User, Admin
from utils.logger import log, log_error

class UserService:
    def __init__(self):
        self.users = []
        log("UserService initialized")
    
    def create_user(self, name, email):
        user = User(name=name, email=email)
        user.validate()
        self.users.append(user)
        log(f"User created: {name}")
        return user
    
    def create_admin(self, name, email):
        admin = Admin(name=name, email=email)
        admin.validate()
        self.users.append(admin)
        log(f"Admin created: {name}")
        return admin
    
    def get_all_users(self):
        return [u.to_dict() for u in self.users]
    
    def find_by_name(self, name):
        for user in self.users:
            if user.name == name:
                return user
        log_error(f"User not found: {name}")
        return None
