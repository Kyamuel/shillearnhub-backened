import os
from datetime import timedelta

class Config:
    # Base configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@shillearnhub.com'
    
    # Redis and Celery
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    
    # Payment settings
    MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY')
    MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET')
    MPESA_API_URL = os.environ.get('MPESA_API_URL') or 'https://sandbox.safaricom.co.ke'
    MPESA_BUSINESS_SHORTCODE = os.environ.get('MPESA_BUSINESS_SHORTCODE') or '174379'
    MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY') or 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'
    MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL') or 'https://example.com/api/payment/mpesa/callback'
    
    PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
    PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET')
    PAYPAL_MODE = os.environ.get('PAYPAL_MODE') or 'sandbox'
    
    # Application settings
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    
    # Membership tiers (in KES)
    MEMBERSHIP_TIERS = {
        'basic': {
            'price': 3500,  # KSh per year
            'daily_missions': 1,
            'referral_levels': 3
        },
        'plus': {
            'price': 10500,  # KSh per year
            'daily_missions': 3,
            'referral_levels': 3
        },
        'pro': {
            'price': 14000,  # KSh per year
            'daily_missions': 4,
            'referral_levels': 4
        },
        'prime': {
            'price': 35000,  # KSh per year
            'daily_missions': 10,
            'referral_levels': 4
        },
        'advanced': {
            'price': 70000,  # KSh per year
            'daily_missions': 20,
            'referral_levels': 4
        },
        'max': {
            'price': 150000,  # KSh per year
            'daily_missions': 40,
            'referral_levels': 5
        }
    }
    
    # Minimum withdrawal amount (in KES)
    MIN_WITHDRAWAL_AMOUNT = 500
    
    # Referral commission rates (percentage of membership fee)
    REFERRAL_COMMISSION_RATES = {
        1: 10,  # Level 1: 10%
        2: 5,   # Level 2: 5%
        3: 3,   # Level 3: 3%
        4: 2,   # Level 4: 2%
        5: 1    # Level 5: 1%
    }

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shillearnhub_dev.db')

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shillearnhub_test.db')

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://user:password@localhost/shillearnhub'
    
    # Override these in production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}