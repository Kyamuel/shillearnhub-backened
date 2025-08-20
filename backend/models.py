from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import pyotp

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    phone_number = db.Column(db.String(20), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    profile_picture = db.Column(db.String(255))
    date_of_birth = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    otp_secret = db.Column(db.String(16))
    otp_valid_until = db.Column(db.DateTime)
    email_verified = db.Column(db.Boolean, default=False)
    phone_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    membership = db.relationship('Membership', backref='user', uselist=False)
    wallet = db.relationship('Wallet', backref='user', uselist=False)
    missions_completed = db.relationship('MissionCompletion', backref='user')
    referrals = db.relationship('Referral', backref='referrer', foreign_keys='Referral.referrer_id')
    referred_by = db.relationship('Referral', backref='referred', foreign_keys='Referral.referred_id', uselist=False)
    withdrawals = db.relationship('Withdrawal', backref='user')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        self.otp_secret = pyotp.random_base32()
        if self.wallet is None:
            self.wallet = Wallet(balance=0)
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_otp(self):
        """Generate a new OTP valid for 10 minutes"""
        self.otp_valid_until = datetime.utcnow() + timedelta(minutes=10)
        totp = pyotp.TOTP(self.otp_secret, interval=600)  # 10 minutes
        return totp.now()
    
    def verify_otp(self, otp):
        """Verify the provided OTP"""
        if datetime.utcnow() > self.otp_valid_until:
            return False
        totp = pyotp.TOTP(self.otp_secret, interval=600)  # 10 minutes
        return totp.verify(otp)
    
    def get_referral_tree(self, max_depth=None):
        """Get the user's referral tree up to max_depth levels"""
        if max_depth is None:
            if self.membership:
                max_depth = self.membership.tier.referral_levels
            else:
                max_depth = 0
        
        if max_depth <= 0:
            return []
        
        result = []
        direct_referrals = Referral.query.filter_by(referrer_id=self.id).all()
        
        for referral in direct_referrals:
            referred_user = User.query.get(referral.referred_id)
            result.append({
                'user': referred_user,
                'level': 1,
                'referrals': referred_user.get_referral_tree(max_depth - 1) if max_depth > 1 else []
            })
        
        return result
    
    def get_available_missions(self):
        """Get missions available to the user based on their membership tier"""
        if not self.membership or not self.membership.is_active:
            return []
        
        # Get completed missions for today
        today = datetime.utcnow().date()
        completed_today = MissionCompletion.query.filter(
            MissionCompletion.user_id == self.id,
            db.func.date(MissionCompletion.completed_at) == today
        ).count()
        
        # Check if user has reached their daily mission limit
        daily_limit = self.membership.tier.daily_missions
        if completed_today >= daily_limit:
            return []
        
        # Get available missions
        available_missions = Mission.query.filter(
            Mission.is_active == True,
            ~Mission.id.in_(
                db.session.query(MissionCompletion.mission_id).filter(
                    MissionCompletion.user_id == self.id,
                    db.func.date(MissionCompletion.completed_at) == today
                )
            )
        ).limit(daily_limit - completed_today).all()
        
        return available_missions

class MembershipTier(db.Model):
    __tablename__ = 'membership_tiers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    price = db.Column(db.Integer)  # Price in KES
    daily_missions = db.Column(db.Integer)
    referral_levels = db.Column(db.Integer)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    memberships = db.relationship('Membership', backref='tier')

class Membership(db.Model):
    __tablename__ = 'memberships'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    tier_id = db.Column(db.Integer, db.ForeignKey('membership_tiers.id'))
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    payment_id = db.Column(db.String(128))  # Reference to payment
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super(Membership, self).__init__(**kwargs)
        if 'end_date' not in kwargs:
            # Default to 1 year membership
            self.end_date = datetime.utcnow() + timedelta(days=365)
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.end_date

class Mission(db.Model):
    __tablename__ = 'missions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128))
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    reward = db.Column(db.Integer)  # Reward in KES
    type = db.Column(db.String(64))  # ad, social, survey, etc.
    content_url = db.Column(db.String(255))  # URL to content
    duration = db.Column(db.Integer)  # Duration in seconds
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    completions = db.relationship('MissionCompletion', backref='mission')

class MissionCompletion(db.Model):
    __tablename__ = 'mission_completions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    mission_id = db.Column(db.Integer, db.ForeignKey('missions.id'))
    reward = db.Column(db.Integer)  # Actual reward paid
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    proof = db.Column(db.Text)  # Proof of completion (if needed)
    
    def __init__(self, **kwargs):
        super(MissionCompletion, self).__init__(**kwargs)
        if 'reward' not in kwargs and 'mission_id' in kwargs:
            mission = Mission.query.get(kwargs['mission_id'])
            if mission:
                self.reward = mission.reward

class Referral(db.Model):
    __tablename__ = 'referrals'
    
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    referred_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    level = db.Column(db.Integer)  # Referral level
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    commissions = db.relationship('ReferralCommission', backref='referral')

class ReferralCommission(db.Model):
    __tablename__ = 'referral_commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    referral_id = db.Column(db.Integer, db.ForeignKey('referrals.id'))
    amount = db.Column(db.Integer)  # Amount in KES
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Wallet(db.Model):
    __tablename__ = 'wallets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    balance = db.Column(db.Integer, default=0)  # Balance in KES
    total_earned = db.Column(db.Integer, default=0)  # Total earned in KES
    total_withdrawn = db.Column(db.Integer, default=0)  # Total withdrawn in KES
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('WalletTransaction', backref='wallet')
    
    def add_funds(self, amount, description):
        """Add funds to wallet and create transaction record"""
        self.balance += amount
        self.total_earned += amount
        
        transaction = WalletTransaction(
            wallet_id=self.id,
            amount=amount,
            type='credit',
            description=description
        )
        db.session.add(transaction)
        return transaction
    
    def deduct_funds(self, amount, description):
        """Deduct funds from wallet and create transaction record"""
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        
        self.balance -= amount
        
        transaction = WalletTransaction(
            wallet_id=self.id,
            amount=amount,
            type='debit',
            description=description
        )
        db.session.add(transaction)
        return transaction

class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallets.id'))
    amount = db.Column(db.Integer)  # Amount in KES
    type = db.Column(db.String(10))  # credit or debit
    description = db.Column(db.String(255))
    reference = db.Column(db.String(128))  # External reference
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Withdrawal(db.Model):
    __tablename__ = 'withdrawals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    amount = db.Column(db.Integer)  # Amount in KES
    method = db.Column(db.String(64))  # mpesa, bank, paypal
    status = db.Column(db.String(20))  # pending, completed, failed
    reference = db.Column(db.String(128))  # Payment reference
    account_info = db.Column(db.String(255))  # Account info for payment
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    def __init__(self, **kwargs):
        super(Withdrawal, self).__init__(**kwargs)
        if 'status' not in kwargs:
            self.status = 'pending'

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    amount = db.Column(db.Integer)  # Amount in KES
    method = db.Column(db.String(64))  # mpesa, card, paypal
    status = db.Column(db.String(20))  # pending, completed, failed
    reference = db.Column(db.String(128))  # Payment reference
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    def __init__(self, **kwargs):
        super(Payment, self).__init__(**kwargs)
        if 'status' not in kwargs:
            self.status = 'pending'

class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128))
    content = db.Column(db.Text)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    image_url = db.Column(db.String(255))
    is_published = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', backref='blog_posts')

class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subject = db.Column(db.String(128))
    message = db.Column(db.Text)
    status = db.Column(db.String(20))  # open, in_progress, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='support_tickets')
    responses = db.relationship('TicketResponse', backref='ticket')

class TicketResponse(db.Model):
    __tablename__ = 'ticket_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Can be admin or user
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='ticket_responses')