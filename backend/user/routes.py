from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta

from models import db, User, Membership, MembershipTier, Referral
from user.utils import allowed_file, get_referral_stats

user_bp = Blueprint('user', __name__)

@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get membership info
    membership_info = None
    if user.membership and user.membership.is_active:
        membership_info = {
            'tier': user.membership.tier.name,
            'start_date': user.membership.start_date.strftime('%Y-%m-%d'),
            'end_date': user.membership.end_date.strftime('%Y-%m-%d'),
            'is_active': user.membership.is_active,
            'daily_missions': user.membership.tier.daily_missions,
            'referral_levels': user.membership.tier.referral_levels
        }
    
    # Get wallet info
    wallet_info = None
    if user.wallet:
        wallet_info = {
            'balance': user.wallet.balance,
            'total_earned': user.wallet.total_earned,
            'total_withdrawn': user.wallet.total_withdrawn
        }
    
    # Get referral stats
    referral_stats = get_referral_stats(user.id)
    
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone_number': user.phone_number,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'profile_picture': user.profile_picture,
            'date_of_birth': user.date_of_birth.strftime('%Y-%m-%d') if user.date_of_birth else None,
            'email_verified': user.email_verified,
            'phone_verified': user.phone_verified,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_admin': user.is_admin
        },
        'membership': membership_info,
        'wallet': wallet_info,
        'referrals': referral_stats
    }), 200

@user_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    # Update allowed fields
    allowed_fields = ['first_name', 'last_name', 'date_of_birth']
    for field in allowed_fields:
        if field in data:
            if field == 'date_of_birth' and data[field]:
                try:
                    setattr(user, field, datetime.strptime(data[field], '%Y-%m-%d'))
                except ValueError:
                    return jsonify({'error': 'Invalid date format for date_of_birth'}), 400
            else:
                setattr(user, field, data[field])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_of_birth': user.date_of_birth.strftime('%Y-%m-%d') if user.date_of_birth else None
        }
    }), 200

@user_bp.route('/profile/picture', methods=['POST'])
@jwt_required()
def update_profile_picture():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{user.id}_{int(datetime.utcnow().timestamp())}_{file.filename}")
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pictures', filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        file.save(file_path)
        
        # Update user profile picture path
        user.profile_picture = f"/static/uploads/profile_pictures/{filename}"
        db.session.commit()
        
        return jsonify({
            'message': 'Profile picture updated successfully',
            'profile_picture': user.profile_picture
        }), 200
    
    return jsonify({'error': 'File type not allowed'}), 400

@user_bp.route('/membership/tiers', methods=['GET'])
def get_membership_tiers():
    tiers = MembershipTier.query.filter_by(is_active=True).all()
    
    result = []
    for tier in tiers:
        result.append({
            'id': tier.id,
            'name': tier.name,
            'price': tier.price,
            'daily_missions': tier.daily_missions,
            'referral_levels': tier.referral_levels,
            'description': tier.description
        })
    
    return jsonify({'tiers': result}), 200

@user_bp.route('/membership/purchase', methods=['POST'])
@jwt_required()
def purchase_membership():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    if 'tier_id' not in data:
        return jsonify({'error': 'Tier ID is required'}), 400
    
    tier = MembershipTier.query.get(data['tier_id'])
    if not tier or not tier.is_active:
        return jsonify({'error': 'Invalid or inactive membership tier'}), 400
    
    # Check if user already has an active membership
    if user.membership and user.membership.is_active and not user.membership.is_expired:
        return jsonify({'error': 'User already has an active membership'}), 400
    
    # Create payment intent (this would be handled by payment module)
    # For now, just return the payment details
    
    return jsonify({
        'message': 'Proceed to payment',
        'payment_details': {
            'amount': tier.price,
            'currency': 'KES',
            'description': f"{tier.name} Membership - 1 Year",
            'tier_id': tier.id,
            'user_id': user.id
        }
    }), 200

@user_bp.route('/referrals', methods=['GET'])
@jwt_required()
def get_referrals():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get direct referrals (level 1)
    direct_referrals = Referral.query.filter_by(referrer_id=user.id, level=1).all()
    
    result = []
    for referral in direct_referrals:
        referred_user = User.query.get(referral.referred_id)
        if referred_user:
            result.append({
                'id': referred_user.id,
                'username': referred_user.username,
                'date_joined': referred_user.created_at.strftime('%Y-%m-%d'),
                'has_membership': referred_user.membership is not None and referred_user.membership.is_active
            })
    
    # Get referral stats
    stats = get_referral_stats(user.id)
    
    return jsonify({
        'referrals': result,
        'stats': stats,
        'referral_code': user.username  # Using username as referral code
    }), 200