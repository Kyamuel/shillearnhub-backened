from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid
import re

from models import db, User, Wallet, Referral
from auth.utils import send_otp_email, send_otp_sms, validate_email, validate_phone

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'phone_number', 'password', 'first_name', 'last_name']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Validate email format
    if not validate_email(data['email']):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Validate phone number format
    if not validate_phone(data['phone_number']):
        return jsonify({'error': 'Invalid phone number format'}), 400
    
    # Check if username, email or phone already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    if User.query.filter_by(phone_number=data['phone_number']).first():
        return jsonify({'error': 'Phone number already exists'}), 400
    
    # Create new user
    new_user = User(
        username=data['username'],
        email=data['email'],
        phone_number=data['phone_number'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        password=data['password'],  # This will be hashed by the setter
        date_of_birth=datetime.strptime(data.get('date_of_birth', '1990-01-01'), '%Y-%m-%d') if data.get('date_of_birth') else None
    )
    
    # Create wallet for user
    new_wallet = Wallet(balance=0, total_earned=0, total_withdrawn=0)
    new_user.wallet = new_wallet
    
    # Handle referral if provided
    referral_code = data.get('referral_code')
    if referral_code:
        referrer = User.query.filter_by(username=referral_code).first()
        if referrer:
            # Create direct referral (level 1)
            referral = Referral(referrer_id=referrer.id, referred_id=new_user.id, level=1)
            db.session.add(referral)
            
            # Create indirect referrals (levels 2-5) based on referrer's referrers
            current_referrer = referrer
            for level in range(2, 6):  # Up to 5 levels
                referrer_relation = Referral.query.filter_by(referred_id=current_referrer.id).first()
                if not referrer_relation:
                    break
                
                indirect_referrer = User.query.get(referrer_relation.referrer_id)
                if not indirect_referrer:
                    break
                
                # Check if indirect referrer's membership allows this level
                if indirect_referrer.membership and indirect_referrer.membership.tier.referral_levels >= level:
                    indirect_referral = Referral(referrer_id=indirect_referrer.id, referred_id=new_user.id, level=level)
                    db.session.add(indirect_referral)
                
                current_referrer = indirect_referrer
    
    db.session.add(new_user)
    db.session.commit()
    
    # Generate OTP and send to email and phone
    otp = new_user.generate_otp()
    send_otp_email(new_user.email, otp)
    send_otp_sms(new_user.phone_number, otp)
    
    return jsonify({
        'message': 'User registered successfully',
        'user_id': new_user.id,
        'username': new_user.username,
        'verification_required': True
    }), 201

@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    
    if 'user_id' not in data or 'otp' not in data:
        return jsonify({'error': 'User ID and OTP are required'}), 400
    
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.verify_otp(data['otp']):
        # Mark email and phone as verified
        user.email_verified = True
        user.phone_verified = True
        db.session.commit()
        
        # Generate tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'message': 'Verification successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_admin': user.is_admin,
                'has_membership': user.membership is not None and user.membership.is_active
            }
        }), 200
    else:
        return jsonify({'error': 'Invalid or expired OTP'}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400
    
    # Check if username is actually email or phone
    if '@' in data['username']:
        user = User.query.filter_by(email=data['username']).first()
    elif re.match(r'^\+?[0-9]+$', data['username']):
        user = User.query.filter_by(phone_number=data['username']).first()
    else:
        user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.verify_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 403
    
    # Generate OTP for two-factor authentication
    otp = user.generate_otp()
    
    # Send OTP via email and SMS
    if user.email_verified:
        send_otp_email(user.email, otp)
    
    if user.phone_verified:
        send_otp_sms(user.phone_number, otp)
    
    return jsonify({
        'message': 'OTP sent for verification',
        'user_id': user.id,
        'verification_required': True
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)
    
    return jsonify({
        'access_token': access_token
    }), 200

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    
    if 'email' not in data:
        return jsonify({'error': 'Email is required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        # Don't reveal that the email doesn't exist
        return jsonify({'message': 'If the email exists, a reset link will be sent'}), 200
    
    # Generate OTP for password reset
    otp = user.generate_otp()
    
    # Send OTP via email
    send_otp_email(user.email, otp, template='password_reset')
    
    return jsonify({
        'message': 'Password reset OTP sent',
        'user_id': user.id
    }), 200

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    
    if 'user_id' not in data or 'otp' not in data or 'new_password' not in data:
        return jsonify({'error': 'User ID, OTP, and new password are required'}), 400
    
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.verify_otp(data['otp']):
        # Update password
        user.password = data['new_password']
        db.session.commit()
        
        return jsonify({
            'message': 'Password reset successful'
        }), 200
    else:
        return jsonify({'error': 'Invalid or expired OTP'}), 400

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # JWT blacklisting would be implemented here if needed
    return jsonify({'message': 'Logout successful'}), 200