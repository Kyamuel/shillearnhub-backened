from datetime import datetime
import requests
import json
from flask import current_app

def validate_mpesa_number(phone_number):
    """Validate M-Pesa phone number format"""
    # Remove any spaces or special characters
    phone_number = ''.join(filter(str.isdigit, phone_number))
    
    # Check if it's a valid Kenyan phone number
    if len(phone_number) == 9 and phone_number.startswith('7'):
        return '254' + phone_number
    elif len(phone_number) == 10 and phone_number.startswith('07'):
        return '254' + phone_number[1:]
    elif len(phone_number) == 12 and phone_number.startswith('254'):
        return phone_number
    else:
        return None

def validate_bank_account(account_info):
    """Validate bank account information"""
    required_fields = ['bank_name', 'account_number', 'account_name']
    
    try:
        account_data = json.loads(account_info) if isinstance(account_info, str) else account_info
        
        for field in required_fields:
            if field not in account_data or not account_data[field]:
                return False
        
        return True
    except:
        return False

def validate_paypal_email(email):
    """Validate PayPal email format"""
    import re
    
    # Basic email validation
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(email_pattern.match(email))

def format_currency(amount):
    """Format amount as KES currency"""
    return f"KSh {amount:,}"

def calculate_referral_commission(amount, level):
    """Calculate referral commission based on level"""
    commission_rates = {
        1: 0.10,  # 10% for level 1
        2: 0.05,  # 5% for level 2
        3: 0.03,  # 3% for level 3
        4: 0.02,  # 2% for level 4
        5: 0.01   # 1% for level 5
    }
    
    rate = commission_rates.get(level, 0)
    return int(amount * rate)  # Return as integer (KES)