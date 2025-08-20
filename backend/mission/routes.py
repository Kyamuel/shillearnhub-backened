from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from models import db, User, Mission, MissionCompletion
from mission.utils import validate_mission_completion

mission_bp = Blueprint('mission', __name__)

@mission_bp.route('/', methods=['GET'])
@jwt_required()
def get_available_missions():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if user has active membership
    if not user.membership or not user.membership.is_active or user.membership.is_expired:
        return jsonify({
            'error': 'Active membership required',
            'missions': [],
            'completed_today': 0,
            'daily_limit': 0
        }), 403
    
    # Get available missions
    available_missions = user.get_available_missions()
    
    # Get completed missions for today
    today = datetime.utcnow().date()
    completed_today = MissionCompletion.query.filter(
        MissionCompletion.user_id == user.id,
        db.func.date(MissionCompletion.completed_at) == today
    ).count()
    
    # Get daily mission limit from membership tier
    daily_limit = user.membership.tier.daily_missions
    
    result = []
    for mission in available_missions:
        result.append({
            'id': mission.id,
            'title': mission.title,
            'description': mission.description,
            'reward': mission.reward,
            'type': mission.type,
            'duration': mission.duration
        })
    
    return jsonify({
        'missions': result,
        'completed_today': completed_today,
        'daily_limit': daily_limit
    }), 200

@mission_bp.route('/<int:mission_id>', methods=['GET'])
@jwt_required()
def get_mission_details(mission_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if user has active membership
    if not user.membership or not user.membership.is_active or user.membership.is_expired:
        return jsonify({'error': 'Active membership required'}), 403
    
    mission = Mission.query.get(mission_id)
    if not mission or not mission.is_active:
        return jsonify({'error': 'Mission not found'}), 404
    
    # Check if mission is already completed today
    today = datetime.utcnow().date()
    already_completed = MissionCompletion.query.filter(
        MissionCompletion.user_id == user.id,
        MissionCompletion.mission_id == mission.id,
        db.func.date(MissionCompletion.completed_at) == today
    ).first() is not None
    
    if already_completed:
        return jsonify({'error': 'Mission already completed today'}), 400
    
    return jsonify({
        'mission': {
            'id': mission.id,
            'title': mission.title,
            'description': mission.description,
            'instructions': mission.instructions,
            'reward': mission.reward,
            'type': mission.type,
            'content_url': mission.content_url,
            'duration': mission.duration
        }
    }), 200

@mission_bp.route('/<int:mission_id>/complete', methods=['POST'])
@jwt_required()
def complete_mission(mission_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if user has active membership
    if not user.membership or not user.membership.is_active or user.membership.is_expired:
        return jsonify({'error': 'Active membership required'}), 403
    
    mission = Mission.query.get(mission_id)
    if not mission or not mission.is_active:
        return jsonify({'error': 'Mission not found'}), 404
    
    # Check if mission is already completed today
    today = datetime.utcnow().date()
    already_completed = MissionCompletion.query.filter(
        MissionCompletion.user_id == user.id,
        MissionCompletion.mission_id == mission.id,
        db.func.date(MissionCompletion.completed_at) == today
    ).first() is not None
    
    if already_completed:
        return jsonify({'error': 'Mission already completed today'}), 400
    
    # Check if user has reached daily mission limit
    completed_today = MissionCompletion.query.filter(
        MissionCompletion.user_id == user.id,
        db.func.date(MissionCompletion.completed_at) == today
    ).count()
    
    daily_limit = user.membership.tier.daily_missions
    if completed_today >= daily_limit:
        return jsonify({'error': 'Daily mission limit reached'}), 400
    
    # Validate mission completion
    data = request.get_json()
    proof = data.get('proof', '')
    
    if not validate_mission_completion(mission, proof):
        return jsonify({'error': 'Invalid mission completion proof'}), 400
    
    # Create mission completion record
    completion = MissionCompletion(
        user_id=user.id,
        mission_id=mission.id,
        reward=mission.reward,
        proof=proof
    )
    
    # Add reward to user's wallet
    user.wallet.add_funds(
        amount=mission.reward,
        description=f"Reward for completing mission: {mission.title}"
    )
    
    db.session.add(completion)
    db.session.commit()
    
    return jsonify({
        'message': 'Mission completed successfully',
        'reward': mission.reward,
        'wallet_balance': user.wallet.balance
    }), 200

@mission_bp.route('/history', methods=['GET'])
@jwt_required()
def get_mission_history():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Get mission completions with pagination
    completions = MissionCompletion.query.filter_by(user_id=user.id).order_by(
        MissionCompletion.completed_at.desc()
    ).paginate(page=page, per_page=per_page)
    
    result = []
    for completion in completions.items:
        mission = Mission.query.get(completion.mission_id)
        if mission:
            result.append({
                'id': completion.id,
                'mission_id': mission.id,
                'title': mission.title,
                'reward': completion.reward,
                'completed_at': completion.completed_at.strftime('%Y-%m-%d %H:%M:%S'),
                'type': mission.type
            })
    
    return jsonify({
        'completions': result,
        'total': completions.total,
        'pages': completions.pages,
        'current_page': page
    }), 200