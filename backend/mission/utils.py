from flask import current_app
import json
import re

def validate_mission_completion(mission, proof):
    """Validate mission completion based on mission type and proof"""
    if not proof:
        return False
    
    # Different validation logic based on mission type
    if mission.type == 'ad':
        # For ad watching, proof might be view duration
        try:
            proof_data = json.loads(proof)
            view_duration = proof_data.get('duration', 0)
            return view_duration >= mission.duration * 0.9  # 90% of required duration
        except:
            return False
    
    elif mission.type == 'social':
        # For social engagement, proof might be engagement ID
        try:
            proof_data = json.loads(proof)
            engagement_id = proof_data.get('engagement_id')
            platform = proof_data.get('platform')
            
            # In a real implementation, you would verify with the platform API
            # For now, just check if values are provided
            return bool(engagement_id and platform)
        except:
            return False
    
    elif mission.type == 'survey':
        # For surveys, proof might be survey responses
        try:
            proof_data = json.loads(proof)
            responses = proof_data.get('responses', [])
            
            # Check if all required questions have answers
            return len(responses) > 0
        except:
            return False
    
    # Default validation for other mission types
    return True

def get_mission_stats(user_id):
    """Get mission completion statistics for a user"""
    from models import db, MissionCompletion
    from datetime import datetime, timedelta
    
    # Get today's completions
    today = datetime.utcnow().date()
    today_count = MissionCompletion.query.filter(
        MissionCompletion.user_id == user_id,
        db.func.date(MissionCompletion.completed_at) == today
    ).count()
    
    # Get this week's completions
    week_start = today - timedelta(days=today.weekday())
    week_count = MissionCompletion.query.filter(
        MissionCompletion.user_id == user_id,
        db.func.date(MissionCompletion.completed_at) >= week_start
    ).count()
    
    # Get this month's completions
    month_start = today.replace(day=1)
    month_count = MissionCompletion.query.filter(
        MissionCompletion.user_id == user_id,
        db.func.date(MissionCompletion.completed_at) >= month_start
    ).count()
    
    # Get total earnings from missions
    total_earnings = db.session.query(db.func.sum(MissionCompletion.reward)).filter(
        MissionCompletion.user_id == user_id
    ).scalar() or 0
    
    return {
        'today': today_count,
        'this_week': week_count,
        'this_month': month_count,
        'total_earnings': total_earnings
    }