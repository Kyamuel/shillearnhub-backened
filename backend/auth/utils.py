from flask import current_app, render_template
from flask_mail import Message
import re
import requests
from models import db, User
from app import mail

def validate_email(email):
    """Validate email format"""
    pattern = r'^[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format (Kenyan format)"""
    # Allow +254XXXXXXXXX or 07XXXXXXXX or 01XXXXXXXX format
    pattern = r'^(\+254|0)[17][0-9]{8}$'
    return re.match(pattern, phone) is not None

def send_otp_email(email, otp, template='otp_verification'):
    """Send OTP via email"""
    try:
        subject = 'ShillEarn Hub - Verification Code'
        if template == 'password_reset':
            subject = 'ShillEarn Hub - Password Reset Code'
        
        msg = Message(
            subject,
            recipients=[email],
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        msg.html = render_template(f'emails/{template}.html', otp=otp)
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False

def send_otp_sms(phone, otp):
    """Send OTP via SMS using Africa's Talking API"""
    try:
        # Format phone number to international format if needed
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        
        # This is a placeholder for actual SMS API integration
        # In production, you would use Africa's Talking or similar service
        
        # Example with Africa's Talking
        # url = "https://api.africastalking.com/version1/messaging"
        # headers = {
        #     'ApiKey': current_app.config['AT_API_KEY'],
        #     'Content-Type': 'application/x-www-form-urlencoded',
        #     'Accept': 'application/json'
        # }
        # data = {
        #     'username': current_app.config['AT_USERNAME'],
        #     'to': phone,
        #     'message': f'Your ShillEarn Hub verification code is: {otp}',
        #     'from': current_app.config.get('AT_SHORTCODE', '')
        # }
        # response = requests.post(url, headers=headers, data=data)
        # return response.status_code == 200
        
        # For development, just log the OTP
        current_app.logger.info(f"SMS to {phone}: Your ShillEarn Hub verification code is: {otp}")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send SMS: {str(e)}")
        return False

def generate_referral_code(user_id):
    """Generate a unique referral code for a user"""
    user = User.query.get(user_id)
    if not user:
        return None
    
    # Use username as referral code
    return user.username