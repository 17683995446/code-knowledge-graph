"""验证工具函数"""
import re

def validate_email(email):
    pattern = r'^[\w.-]+@[\w.-]+\.\w+$'
    return bool(re.match(pattern, email))

def validate_phone(phone):
    pattern = r'^\d{11}$'
    return bool(re.match(pattern, phone))

def sanitize_input(text):
    return re.sub(r'[<>&]', '', text)
