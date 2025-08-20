from flask import Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import uuid
import json

from models import db, User, Payment, Membership, MembershipTier
from payment.mpesa import MpesaAPI

payment_bp = Blueprint('payment', __name__)
mpesa_api = MpesaAPI()

@payment_bp.route('/initialize', methods=['POST'])
@jwt_required()
def initialize_payment():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['tier_id', 'payment_method']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Get membership tier
    tier = MembershipTier.query.get(data['tier_id'])
    if not tier or not tier.is_active:
        return jsonify({'error': 'Invalid membership tier'}), 400
    
    # Validate payment method
    payment_method = data['payment_method']
    valid_methods = ['mpesa', 'card', 'paypal']
    if payment_method not in valid_methods:
        return jsonify({'error': f'Invalid payment method. Must be one of: {valid_methods}'}), 400
    
    # Generate payment reference
    reference = f"SLH-{uuid.uuid4().hex[:8].upper()}"
    
    # Create payment record
    payment = Payment(
        user_id=user.id,
        amount=tier.price,
        method=payment_method,
        status='pending',
        reference=reference,
        description=f"Membership: {tier.name}"
    )
    
    db.session.add(payment)
    db.session.commit()
    
    # Initialize payment based on method
    if payment_method == 'mpesa':
        # Validate phone number
        phone_number = data.get('phone_number', user.phone_number)
        if not phone_number:
            return jsonify({'error': 'Phone number is required for M-Pesa payment'}), 400
        
        # Initialize M-Pesa STK push
        result = mpesa_api.initiate_stk_push(
            phone_number=phone_number,
            amount=tier.price,
            reference=reference,
            description=f"ShillEarn Hub {tier.name} Membership"
        )
        
        if result['success']:
            return jsonify({
                'payment_id': payment.id,
                'reference': reference,
                'amount': tier.price,
                'status': 'pending',
                'message': 'Please complete the payment on your phone',
                'checkout_request_id': result.get('checkout_request_id')
            }), 200
        else:
            payment.status = 'failed'
            db.session.commit()
            return jsonify({
                'error': 'Failed to initiate payment',
                'message': result.get('message')
            }), 400
    
    elif payment_method == 'card':
        # For demo purposes, we'll just return a URL to a payment page
        payment_url = url_for('payment.card_payment_page', payment_id=payment.id, _external=True)
        return jsonify({
            'payment_id': payment.id,
            'reference': reference,
            'amount': tier.price,
            'status': 'pending',
            'payment_url': payment_url
        }), 200
    
    elif payment_method == 'paypal':
        # For demo purposes, we'll just return a URL to a payment page
        payment_url = url_for('payment.paypal_payment_page', payment_id=payment.id, _external=True)
        return jsonify({
            'payment_id': payment.id,
            'reference': reference,
            'amount': tier.price,
            'status': 'pending',
            'payment_url': payment_url
        }), 200

@payment_bp.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """Callback endpoint for M-Pesa payments"""
    data = request.get_json()
    reference = request.args.get('reference')
    
    if not reference:
        return jsonify({'error': 'Missing reference'}), 400
    
    # Find the payment by reference
    payment = Payment.query.filter_by(reference=reference).first()
    if not payment:
        return jsonify({'error': 'Payment not found'}), 404
    
    # Process the callback data
    result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
    
    if result_code == 0:  # Success
        # Update payment status
        payment.status = 'completed'
        payment.completed_at = datetime.utcnow()
        
        # Create or update membership
        user = User.query.get(payment.user_id)
        tier_name = payment.description.split(': ')[1] if ': ' in payment.description else None
        
        if tier_name:
            tier = MembershipTier.query.filter_by(name=tier_name).first()
            if tier:
                # Check if user already has a membership
                if user.membership:
                    user.membership.tier_id = tier.id
                    user.membership.start_date = datetime.utcnow()
                    user.membership.end_date = datetime.utcnow() + timedelta(days=365)
                    user.membership.is_active = True
                    user.membership.payment_id = payment.reference
                else:
                    # Create new membership
                    membership = Membership(
                        user_id=user.id,
                        tier_id=tier.id,
                        payment_id=payment.reference
                    )
                    db.session.add(membership)
        
        db.session.commit()
        
        return jsonify({'success': True}), 200
    else:
        # Payment failed
        payment.status = 'failed'
        db.session.commit()
        
        return jsonify({'success': False}), 200

@payment_bp.route('/status/<payment_id>', methods=['GET'])
@jwt_required()
def check_payment_status(payment_id):
    """Check the status of a payment"""
    current_user_id = get_jwt_identity()
    
    payment = Payment.query.get(payment_id)
    if not payment or payment.user_id != current_user_id:
        return jsonify({'error': 'Payment not found'}), 404
    
    # If payment is pending and it's M-Pesa, check status from API
    if payment.status == 'pending' and payment.method == 'mpesa':
        # For demo purposes, we'll just return the current status
        # In a real implementation, you would query the M-Pesa API
        pass
    
    return jsonify({
        'payment_id': payment.id,
        'reference': payment.reference,
        'amount': payment.amount,
        'method': payment.method,
        'status': payment.status,
        'description': payment.description,
        'created_at': payment.created_at.isoformat(),
        'completed_at': payment.completed_at.isoformat() if payment.completed_at else None
    }), 200

@payment_bp.route('/history', methods=['GET'])
@jwt_required()
def payment_history():
    """Get payment history for the current user"""
    current_user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    payments = Payment.query.filter_by(user_id=current_user_id)\
        .order_by(Payment.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for payment in payments.items:
        result.append({
            'payment_id': payment.id,
            'reference': payment.reference,
            'amount': payment.amount,
            'method': payment.method,
            'status': payment.status,
            'description': payment.description,
            'created_at': payment.created_at.isoformat(),
            'completed_at': payment.completed_at.isoformat() if payment.completed_at else None
        })
    
    return jsonify({
        'payments': result,
        'total': payments.total,
        'pages': payments.pages,
        'current_page': page
    }), 200