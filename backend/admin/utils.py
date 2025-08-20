from datetime import datetime, timedelta
from sqlalchemy import func

from models import db, User, Mission, MissionCompletion, Payment, Withdrawal

def get_date_range(days=30):
    """Get start and end date for a given range of days from today"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date

def get_revenue_stats(days=30):
    """Get revenue statistics for a given period"""
    start_date, end_date = get_date_range(days)
    
    # Total revenue in period
    total_revenue = db.session.query(func.sum(Payment.amount))\
        .filter(Payment.status == 'completed')\
        .filter(Payment.completed_at.between(start_date, end_date))\
        .scalar() or 0
    
    # Daily revenue breakdown
    daily_revenue = db.session.query(
            func.date(Payment.completed_at).label('date'),
            func.sum(Payment.amount).label('amount')
        )\
        .filter(Payment.status == 'completed')\
        .filter(Payment.completed_at.between(start_date, end_date))\
        .group_by(func.date(Payment.completed_at))\
        .all()
    
    # Convert to dictionary with date strings as keys
    daily_breakdown = {}
    for date, amount in daily_revenue:
        daily_breakdown[date.strftime('%Y-%m-%d')] = float(amount)
    
    return {
        'total_revenue': float(total_revenue),
        'daily_breakdown': daily_breakdown
    }

def get_user_stats(days=30):
    """Get user statistics for a given period"""
    start_date, end_date = get_date_range(days)
    
    # Total users
    total_users = User.query.count()
    
    # New users in period
    new_users = User.query\
        .filter(User.created_at.between(start_date, end_date))\
        .count()
    
    # Daily new user breakdown
    daily_signups = db.session.query(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('count')
        )\
        .filter(User.created_at.between(start_date, end_date))\
        .group_by(func.date(User.created_at))\
        .all()
    
    # Convert to dictionary with date strings as keys
    daily_breakdown = {}
    for date, count in daily_signups:
        daily_breakdown[date.strftime('%Y-%m-%d')] = count
    
    return {
        'total_users': total_users,
        'new_users': new_users,
        'daily_breakdown': daily_breakdown
    }

def get_mission_stats(days=30):
    """Get mission completion statistics for a given period"""
    start_date, end_date = get_date_range(days)
    
    # Total missions completed in period
    total_completed = MissionCompletion.query\
        .filter(MissionCompletion.completed_at.between(start_date, end_date))\
        .count()
    
    # Total rewards paid in period
    total_rewards = db.session.query(func.sum(MissionCompletion.reward))\
        .filter(MissionCompletion.completed_at.between(start_date, end_date))\
        .scalar() or 0
    
    # Daily mission completion breakdown
    daily_completions = db.session.query(
            func.date(MissionCompletion.completed_at).label('date'),
            func.count(MissionCompletion.id).label('count'),
            func.sum(MissionCompletion.reward).label('rewards')
        )\
        .filter(MissionCompletion.completed_at.between(start_date, end_date))\
        .group_by(func.date(MissionCompletion.completed_at))\
        .all()
    
    # Convert to dictionary with date strings as keys
    daily_breakdown = {}
    for date, count, rewards in daily_completions:
        daily_breakdown[date.strftime('%Y-%m-%d')] = {
            'count': count,
            'rewards': float(rewards)
        }
    
    return {
        'total_completed': total_completed,
        'total_rewards': float(total_rewards),
        'daily_breakdown': daily_breakdown
    }

def get_withdrawal_stats(days=30):
    """Get withdrawal statistics for a given period"""
    start_date, end_date = get_date_range(days)
    
    # Total withdrawals in period
    total_withdrawals = Withdrawal.query\
        .filter(Withdrawal.created_at.between(start_date, end_date))\
        .count()
    
    # Total amount withdrawn in period
    total_amount = db.session.query(func.sum(Withdrawal.amount))\
        .filter(Withdrawal.status == 'completed')\
        .filter(Withdrawal.processed_at.between(start_date, end_date))\
        .scalar() or 0
    
    # Pending withdrawals
    pending_count = Withdrawal.query.filter_by(status='pending').count()
    pending_amount = db.session.query(func.sum(Withdrawal.amount))\
        .filter_by(status='pending')\
        .scalar() or 0
    
    # Withdrawal method breakdown
    method_breakdown = db.session.query(
            Withdrawal.method,
            func.count(Withdrawal.id).label('count'),
            func.sum(Withdrawal.amount).label('amount')
        )\
        .filter(Withdrawal.created_at.between(start_date, end_date))\
        .group_by(Withdrawal.method)\
        .all()
    
    # Convert to dictionary
    methods = {}
    for method, count, amount in method_breakdown:
        methods[method] = {
            'count': count,
            'amount': float(amount)
        }
    
    return {
        'total_withdrawals': total_withdrawals,
        'total_amount': float(total_amount),
        'pending': {
            'count': pending_count,
            'amount': float(pending_amount)
        },
        'methods': methods
    }

def format_currency(amount, currency='KES'):
    """Format currency amount with proper symbol"""
    if currency == 'KES':
        return f"KES {amount:,.2f}"
    return f"{currency} {amount:,.2f}"