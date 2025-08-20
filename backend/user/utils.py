from flask import current_app
from models import db, User, Referral, ReferralCommission, Membership

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def get_referral_stats(user_id):
    """Get referral statistics for a user"""
    user = User.query.get(user_id)
    if not user:
        return None
    
    # Get max referral levels based on membership
    max_levels = 0
    if user.membership and user.membership.is_active:
        max_levels = user.membership.tier.referral_levels
    
    # Initialize stats
    stats = {
        'total_referrals': 0,
        'total_commissions': 0,
        'levels': {}
    }
    
    # Get referrals by level
    for level in range(1, max_levels + 1):
        referrals_count = Referral.query.filter_by(referrer_id=user.id, level=level).count()
        
        # Get commissions for this level
        commissions = db.session.query(db.func.sum(ReferralCommission.amount)).join(
            Referral, Referral.id == ReferralCommission.referral_id
        ).filter(
            Referral.referrer_id == user.id,
            Referral.level == level
        ).scalar() or 0
        
        stats['levels'][level] = {
            'count': referrals_count,
            'commissions': commissions,
            'rate': current_app.config['REFERRAL_COMMISSION_RATES'].get(level, 0)
        }
        
        stats['total_referrals'] += referrals_count
        stats['total_commissions'] += commissions
    
    return stats

def calculate_referral_commission(membership_tier_id, level):
    """Calculate referral commission for a membership purchase"""
    tier = MembershipTier.query.get(membership_tier_id)
    if not tier:
        return 0
    
    # Get commission rate for this level
    rate = current_app.config['REFERRAL_COMMISSION_RATES'].get(level, 0)
    
    # Calculate commission
    commission = int(tier.price * rate / 100)
    
    return commission