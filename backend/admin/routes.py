from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import func

from models import db, User, Mission, MissionCompletion, Membership, MembershipTier, Payment, Withdrawal, Referral

admin_bp = Blueprint('admin', __name__)

# Admin authentication middleware
def admin_required(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        return fn(*args, **kwargs)
    
    # Preserve the original function's name and docstring
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    
    return wrapper

# Dashboard statistics
@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    # Get user statistics
    total_users = User.query.count()
    active_memberships = Membership.query.filter_by(is_active=True).count()
    
    # Get revenue statistics
    total_revenue = db.session.query(func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    
    # Get today's revenue
    today = datetime.utcnow().date()
    today_revenue = db.session.query(func.sum(Payment.amount))\
        .filter(Payment.status == 'completed')\
        .filter(func.date(Payment.completed_at) == today)\
        .scalar() or 0
    
    # Get mission statistics
    total_missions = Mission.query.count()
    active_missions = Mission.query.filter_by(is_active=True).count()
    completed_missions = MissionCompletion.query.count()
    
    # Get today's completed missions
    today_completed = MissionCompletion.query\
        .filter(func.date(MissionCompletion.completed_at) == today)\
        .count()
    
    # Get withdrawal statistics
    pending_withdrawals = Withdrawal.query.filter_by(status='pending').count()
    total_withdrawn = db.session.query(func.sum(Withdrawal.amount))\
        .filter_by(status='completed')\
        .scalar() or 0
    
    # Get membership tier distribution
    tier_distribution = {}
    for tier in MembershipTier.query.all():
        count = Membership.query.filter_by(tier_id=tier.id, is_active=True).count()
        tier_distribution[tier.name] = count
    
    # Get recent registrations (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_registrations = User.query\
        .filter(User.created_at >= week_ago)\
        .count()
    
    return jsonify({
        'user_stats': {
            'total_users': total_users,
            'active_memberships': active_memberships,
            'recent_registrations': recent_registrations
        },
        'revenue_stats': {
            'total_revenue': total_revenue,
            'today_revenue': today_revenue
        },
        'mission_stats': {
            'total_missions': total_missions,
            'active_missions': active_missions,
            'completed_missions': completed_missions,
            'today_completed': today_completed
        },
        'withdrawal_stats': {
            'pending_withdrawals': pending_withdrawals,
            'total_withdrawn': total_withdrawn
        },
        'membership_distribution': tier_distribution
    }), 200

# User management
@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    
    # Apply search filter if provided
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.phone_number.ilike(f'%{search}%')) |
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%'))
        )
    
    users = query.order_by(User.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for user in users.items:
        result.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone_number': user.phone_number,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'is_admin': user.is_admin,
            'email_verified': user.email_verified,
            'phone_verified': user.phone_verified,
            'created_at': user.created_at.isoformat(),
            'has_membership': user.membership is not None,
            'membership_tier': user.membership.tier.name if user.membership else None
        })
    
    return jsonify({
        'users': result,
        'total': users.total,
        'pages': users.pages,
        'current_page': page
    }), 200

@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get user's wallet info
    wallet_info = None
    if user.wallet:
        wallet_info = {
            'balance': user.wallet.balance,
            'total_earned': user.wallet.total_earned,
            'total_withdrawn': user.wallet.total_withdrawn
        }
    
    # Get user's membership info
    membership_info = None
    if user.membership:
        membership_info = {
            'tier': user.membership.tier.name,
            'start_date': user.membership.start_date.isoformat(),
            'end_date': user.membership.end_date.isoformat(),
            'is_active': user.membership.is_active,
            'is_expired': user.membership.is_expired
        }
    
    # Get user's referral info
    referrals = Referral.query.filter_by(referrer_id=user.id).all()
    referral_info = {
        'total_referrals': len(referrals),
        'referrals_by_level': {}
    }
    
    for referral in referrals:
        level = referral.level
        if level not in referral_info['referrals_by_level']:
            referral_info['referrals_by_level'][level] = 0
        referral_info['referrals_by_level'][level] += 1
    
    # Get user's mission completion stats
    mission_stats = {
        'total_completed': MissionCompletion.query.filter_by(user_id=user.id).count(),
        'total_earned': db.session.query(func.sum(MissionCompletion.reward))\
            .filter_by(user_id=user.id).scalar() or 0
    }
    
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone_number': user.phone_number,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'profile_picture': user.profile_picture,
            'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
            'is_active': user.is_active,
            'is_admin': user.is_admin,
            'email_verified': user.email_verified,
            'phone_verified': user.phone_verified,
            'created_at': user.created_at.isoformat(),
            'updated_at': user.updated_at.isoformat()
        },
        'wallet': wallet_info,
        'membership': membership_info,
        'referrals': referral_info,
        'mission_stats': mission_stats
    }), 200

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    # Update user fields
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    if 'is_admin' in data:
        user.is_admin = data['is_admin']
    
    if 'email_verified' in data:
        user.email_verified = data['email_verified']
    
    if 'phone_verified' in data:
        user.phone_verified = data['phone_verified']
    
    db.session.commit()
    
    return jsonify({
        'message': 'User updated successfully',
        'user_id': user.id
    }), 200

# Mission management
@admin_bp.route('/missions', methods=['GET'])
@admin_required
def get_missions():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    missions = Mission.query.order_by(Mission.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for mission in missions.items:
        result.append({
            'id': mission.id,
            'title': mission.title,
            'description': mission.description,
            'reward': mission.reward,
            'type': mission.type,
            'is_active': mission.is_active,
            'created_at': mission.created_at.isoformat(),
            'completions_count': len(mission.completions)
        })
    
    return jsonify({
        'missions': result,
        'total': missions.total,
        'pages': missions.pages,
        'current_page': page
    }), 200

@admin_bp.route('/missions', methods=['POST'])
@admin_required
def create_mission():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['title', 'description', 'instructions', 'reward', 'type', 'content_url', 'duration']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Create new mission
    mission = Mission(
        title=data['title'],
        description=data['description'],
        instructions=data['instructions'],
        reward=data['reward'],
        type=data['type'],
        content_url=data['content_url'],
        duration=data['duration'],
        is_active=data.get('is_active', True)
    )
    
    db.session.add(mission)
    db.session.commit()
    
    return jsonify({
        'message': 'Mission created successfully',
        'mission_id': mission.id
    }), 201

@admin_bp.route('/missions/<int:mission_id>', methods=['PUT'])
@admin_required
def update_mission(mission_id):
    mission = Mission.query.get(mission_id)
    if not mission:
        return jsonify({'error': 'Mission not found'}), 404
    
    data = request.get_json()
    
    # Update mission fields
    if 'title' in data:
        mission.title = data['title']
    
    if 'description' in data:
        mission.description = data['description']
    
    if 'instructions' in data:
        mission.instructions = data['instructions']
    
    if 'reward' in data:
        mission.reward = data['reward']
    
    if 'type' in data:
        mission.type = data['type']
    
    if 'content_url' in data:
        mission.content_url = data['content_url']
    
    if 'duration' in data:
        mission.duration = data['duration']
    
    if 'is_active' in data:
        mission.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Mission updated successfully',
        'mission_id': mission.id
    }), 200

# Withdrawal management
@admin_bp.route('/withdrawals', methods=['GET'])
@admin_required
def get_withdrawals():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    
    query = Withdrawal.query
    
    # Filter by status if provided
    if status:
        query = query.filter_by(status=status)
    
    withdrawals = query.order_by(Withdrawal.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for withdrawal in withdrawals.items:
        user = User.query.get(withdrawal.user_id)
        result.append({
            'id': withdrawal.id,
            'user_id': withdrawal.user_id,
            'username': user.username if user else 'Unknown',
            'amount': withdrawal.amount,
            'method': withdrawal.method,
            'status': withdrawal.status,
            'account_info': withdrawal.account_info,
            'created_at': withdrawal.created_at.isoformat(),
            'processed_at': withdrawal.processed_at.isoformat() if withdrawal.processed_at else None
        })
    
    return jsonify({
        'withdrawals': result,
        'total': withdrawals.total,
        'pages': withdrawals.pages,
        'current_page': page
    }), 200

@admin_bp.route('/withdrawals/<int:withdrawal_id>', methods=['PUT'])
@admin_required
def process_withdrawal(withdrawal_id):
    withdrawal = Withdrawal.query.get(withdrawal_id)
    if not withdrawal:
        return jsonify({'error': 'Withdrawal not found'}), 404
    
    data = request.get_json()
    
    # Update withdrawal status
    if 'status' in data:
        new_status = data['status']
        if new_status not in ['pending', 'completed', 'failed']:
            return jsonify({'error': 'Invalid status'}), 400
        
        # If marking as completed or failed
        if new_status != 'pending' and withdrawal.status == 'pending':
            withdrawal.processed_at = datetime.utcnow()
            
            # If failed, refund the amount to user's wallet
            if new_status == 'failed':
                user = User.query.get(withdrawal.user_id)
                if user and user.wallet:
                    user.wallet.add_funds(
                        withdrawal.amount,
                        'Refund for failed withdrawal'
                    )
        
        withdrawal.status = new_status
        db.session.commit()
    
    return jsonify({
        'message': 'Withdrawal updated successfully',
        'withdrawal_id': withdrawal.id,
        'status': withdrawal.status
    }), 200

# Membership tier management
@admin_bp.route('/membership-tiers', methods=['GET'])
@admin_required
def get_membership_tiers():
    tiers = MembershipTier.query.all()
    
    result = []
    for tier in tiers:
        result.append({
            'id': tier.id,
            'name': tier.name,
            'price': tier.price,
            'daily_missions': tier.daily_missions,
            'referral_levels': tier.referral_levels,
            'description': tier.description,
            'is_active': tier.is_active,
            'created_at': tier.created_at.isoformat(),
            'updated_at': tier.updated_at.isoformat()
        })
    
    return jsonify({'tiers': result}), 200

@admin_bp.route('/membership-tiers', methods=['POST'])
@admin_required
def create_membership_tier():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'price', 'daily_missions', 'referral_levels', 'description']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Check if tier with same name already exists
    existing_tier = MembershipTier.query.filter_by(name=data['name']).first()
    if existing_tier:
        return jsonify({'error': 'Membership tier with this name already exists'}), 400
    
    # Create new tier
    tier = MembershipTier(
        name=data['name'],
        price=data['price'],
        daily_missions=data['daily_missions'],
        referral_levels=data['referral_levels'],
        description=data['description'],
        is_active=data.get('is_active', True)
    )
    
    db.session.add(tier)
    db.session.commit()
    
    return jsonify({
        'message': 'Membership tier created successfully',
        'tier_id': tier.id
    }), 201

@admin_bp.route('/membership-tiers/<int:tier_id>', methods=['PUT'])
@admin_required
def update_membership_tier(tier_id):
    tier = MembershipTier.query.get(tier_id)
    if not tier:
        return jsonify({'error': 'Membership tier not found'}), 404
    
    data = request.get_json()
    
    # Update tier fields
    if 'name' in data:
        # Check if another tier with this name exists
        existing_tier = MembershipTier.query.filter_by(name=data['name']).first()
        if existing_tier and existing_tier.id != tier.id:
            return jsonify({'error': 'Another membership tier with this name already exists'}), 400
        tier.name = data['name']
    
    if 'price' in data:
        tier.price = data['price']
    
    if 'daily_missions' in data:
        tier.daily_missions = data['daily_missions']
    
    if 'referral_levels' in data:
        tier.referral_levels = data['referral_levels']
    
    if 'description' in data:
        tier.description = data['description']
    
    if 'is_active' in data:
        tier.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Membership tier updated successfully',
        'tier_id': tier.id
    }), 200