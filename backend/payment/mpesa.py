import requests
import base64
import json
from datetime import datetime
import pytz
from flask import current_app

class MpesaAPI:
    """Class to handle M-Pesa API integration"""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.consumer_key = app.config.get('MPESA_CONSUMER_KEY')
        self.consumer_secret = app.config.get('MPESA_CONSUMER_SECRET')
        self.business_shortcode = app.config.get('MPESA_BUSINESS_SHORTCODE')
        self.passkey = app.config.get('MPESA_PASSKEY')
        self.callback_url = app.config.get('MPESA_CALLBACK_URL')
        
        # API endpoints
        self.auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        self.stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        self.query_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    
    def get_access_token(self):
        """Get OAuth access token"""
        auth_string = f"{self.consumer_key}:{self.consumer_secret}"
        auth_bytes = auth_string.encode("ascii")
        encoded_auth = base64.b64encode(auth_bytes).decode("ascii")
        
        headers = {
            "Authorization": f"Basic {encoded_auth}"
        }
        
        try:
            response = requests.get(self.auth_url, headers=headers)
            response_data = response.json()
            return response_data.get("access_token")
        except Exception as e:
            current_app.logger.error(f"Error getting access token: {str(e)}")
            return None
    
    def generate_password(self):
        """Generate password for STK push"""
        timestamp = datetime.now(pytz.timezone('Africa/Nairobi')).strftime('%Y%m%d%H%M%S')
        password_str = f"{self.business_shortcode}{self.passkey}{timestamp}"
        password_bytes = password_str.encode('ascii')
        return base64.b64encode(password_bytes).decode('utf-8'), timestamp
    
    def initiate_stk_push(self, phone_number, amount, reference, description):
        """Initiate STK push to customer's phone"""
        access_token = self.get_access_token()
        if not access_token:
            return {
                "success": False,
                "message": "Failed to get access token"
            }
        
        password, timestamp = self.generate_password()
        
        # Format phone number (remove leading 0 or +254)
        if phone_number.startswith("0"):
            phone_number = "254" + phone_number[1:]
        elif phone_number.startswith("+254"):
            phone_number = phone_number[1:]
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": self.business_shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": f"{self.callback_url}?reference={reference}",
            "AccountReference": reference,
            "TransactionDesc": description
        }
        
        try:
            response = requests.post(self.stk_push_url, json=payload, headers=headers)
            response_data = response.json()
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "checkout_request_id": response_data.get("CheckoutRequestID"),
                    "response_code": response_data.get("ResponseCode"),
                    "message": response_data.get("ResponseDescription")
                }
            else:
                return {
                    "success": False,
                    "message": response_data.get("errorMessage", "Unknown error")
                }
        except Exception as e:
            current_app.logger.error(f"Error initiating STK push: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def query_stk_status(self, checkout_request_id):
        """Query status of an STK push request"""
        access_token = self.get_access_token()
        if not access_token:
            return {
                "success": False,
                "message": "Failed to get access token"
            }
        
        password, timestamp = self.generate_password()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        try:
            response = requests.post(self.query_url, json=payload, headers=headers)
            response_data = response.json()
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "result_code": response_data.get("ResultCode"),
                    "result_desc": response_data.get("ResultDesc")
                }
            else:
                return {
                    "success": False,
                    "message": response_data.get("errorMessage", "Unknown error")
                }
        except Exception as e:
            current_app.logger.error(f"Error querying STK status: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }