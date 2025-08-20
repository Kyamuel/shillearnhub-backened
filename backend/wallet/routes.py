from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from models import db, User, Wallet, WalletTransaction, Withdrawal

wallet_bp = Blueprint('wallet', __name__)

@wallet_bp.route('/', methods=['GET'])
@jwt_required()
def get_wallet():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if not user.wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    # Get recent transactions
    recent_transactions = WalletTransaction.query.filter_by(wallet_id=user.wallet.id)\
        .order_by(WalletTransaction.created_at.desc()).limit(10).all()
    
    transactions = []
    for transaction in recent_transactions:
        transactions.append({
            'id': transaction.id,
            'amount': transaction.amount,
            'type': transaction.type,
            'description': transaction.description,
            'created_at': transaction.created_at.isoformat()
        })
    
    return jsonify({
        'wallet': {
            'balance': user.wallet.balance,
            'total_earned': user.wallet.total_earned,
            'total_withdrawn': user.wallet.total_withdrawn,
            'recent_transactions': transactions
        }
    }), 200

@wallet_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user or not user.wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    transactions = WalletTransaction.query.filter_by(wallet_id=user.wallet.id)\
        .order_by(WalletTransaction.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for transaction in transactions.items:
        result.append({
            'id': transaction.id,
            'amount': transaction.amount,
            'type': transaction.type,
            'description': transaction.description,
            'reference': transaction.reference,
            'created_at': transaction.created_at.isoformat()
        })
    
    return jsonify({
        'transactions': result,
        'total': transactions.total,
        'pages': transactions.pages,
        'current_page': page
    }), 200

@wallet_bp.route('/withdraw', methods=['POST'])
@jwt_required()
def request_withdrawal():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user or not user.wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['amount', 'method', 'account_info']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Validate amount
    amount = data['amount']
    if not isinstance(amount, int) or amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    
    # Check if user has sufficient balance
    if user.wallet.balance < amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Validate withdrawal method
    method = data['method']
    valid_methods = ['mpesa', 'bank', 'paypal']
    if method not in valid_methods:
        return jsonify({'error': f'Invalid method. Must be one of: {valid_methods}'}), 400
    
    # Create withdrawal request
    withdrawal = Withdrawal(
        user_id=user.id,
        amount=amount,
        method=method,
        account_info=data['account_info'],
        status='pending'
    )
    
    # Deduct funds from wallet
    try:
        user.wallet.deduct_funds(amount, f'Withdrawal request via {method}')
        db.session.add(withdrawal)
        db.session.commit()
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    return jsonify({
        'message': 'Withdrawal request submitted successfully',
        'withdrawal_id': withdrawal.id,
        'status': withdrawal.status
    }), 201

@wallet_bp.route('/withdrawals', methods=['GET'])
@jwt_required()
def get_withdrawals():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    withdrawals = Withdrawal.query.filter_by(user_id=user.id)\
        .order_by(Withdrawal.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for withdrawal in withdrawals.items:
        result.append({
            'id': withdrawal.id,
            'amount': withdrawal.amount,
            'method': withdrawal.method,
            'status': withdrawal.status,
            'created_at': withdrawal.created_at.isoformat(),
            'processed_at': withdrawal.processed_at.isoformat() if withdrawal.processed_at else None
        })
    
    return jsonify({
        'withdrawals': result,
        'total': withdrawals.total,
        'pages': withdrawals.pages,
        'current_page': page
    }), 200