from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import desc

from models import db, SupportTicket, TicketResponse, User
from admin.routes import admin_required

support_bp = Blueprint('support', __name__)

# User routes for support tickets

# Get user's tickets
@support_bp.route('/tickets', methods=['GET'])
@jwt_required()
def get_user_tickets():
    current_user_id = get_jwt_identity()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status')  # 'open', 'closed', 'all'
    
    query = SupportTicket.query.filter_by(user_id=current_user_id)
    
    # Filter by status if provided
    if status == 'open':
        query = query.filter_by(status='open')
    elif status == 'closed':
        query = query.filter_by(status='closed')
    
    tickets = query.order_by(desc(SupportTicket.created_at))\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for ticket in tickets.items:
        # Count responses
        response_count = TicketResponse.query.filter_by(ticket_id=ticket.id).count()
        
        # Get latest response date
        latest_response = TicketResponse.query\
            .filter_by(ticket_id=ticket.id)\
            .order_by(desc(TicketResponse.created_at))\
            .first()
        
        result.append({
            'id': ticket.id,
            'subject': ticket.subject,
            'category': ticket.category,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat(),
            'response_count': response_count,
            'latest_response': latest_response.created_at.isoformat() if latest_response else None
        })
    
    return jsonify({
        'tickets': result,
        'total': tickets.total,
        'pages': tickets.pages,
        'current_page': page
    }), 200

# Create a new support ticket
@support_bp.route('/tickets', methods=['POST'])
@jwt_required()
def create_ticket():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['subject', 'message', 'category']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Create new ticket
    ticket = SupportTicket(
        user_id=current_user_id,
        subject=data['subject'],
        category=data['category'],
        status='open'
    )
    
    db.session.add(ticket)
    db.session.flush()  # Get ticket ID before committing
    
    # Create initial message
    response = TicketResponse(
        ticket_id=ticket.id,
        user_id=current_user_id,
        message=data['message'],
        is_from_admin=False
    )
    
    db.session.add(response)
    db.session.commit()
    
    return jsonify({
        'message': 'Support ticket created successfully',
        'ticket_id': ticket.id
    }), 201

# Get a specific ticket with responses
@support_bp.route('/tickets/<int:ticket_id>', methods=['GET'])
@jwt_required()
def get_ticket(ticket_id):
    current_user_id = get_jwt_identity()
    
    # Get the ticket
    ticket = SupportTicket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket not found'}), 404
    
    # Check if ticket belongs to current user
    if ticket.user_id != current_user_id:
        return jsonify({'error': 'Unauthorized access to ticket'}), 403
    
    # Get ticket responses
    responses = TicketResponse.query\
        .filter_by(ticket_id=ticket.id)\
        .order_by(TicketResponse.created_at)\
        .all()
    
    response_list = []
    for resp in responses:
        # Get user info for response
        user = User.query.get(resp.user_id)
        
        response_list.append({
            'id': resp.id,
            'message': resp.message,
            'created_at': resp.created_at.isoformat(),
            'is_from_admin': resp.is_from_admin,
            'user': {
                'id': user.id,
                'name': f"{user.first_name} {user.last_name}",
                'profile_picture': user.profile_picture
            }
        })
    
    return jsonify({
        'ticket': {
            'id': ticket.id,
            'subject': ticket.subject,
            'category': ticket.category,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat()
        },
        'responses': response_list
    }), 200

# Add a response to a ticket
@support_bp.route('/tickets/<int:ticket_id>/respond', methods=['POST'])
@jwt_required()
def respond_to_ticket(ticket_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate message
    if 'message' not in data or not data['message'].strip():
        return jsonify({'error': 'Message is required'}), 400
    
    # Get the ticket
    ticket = SupportTicket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket not found'}), 404
    
    # Check if ticket belongs to current user
    if ticket.user_id != current_user_id:
        return jsonify({'error': 'Unauthorized access to ticket'}), 403
    
    # Check if ticket is open
    if ticket.status != 'open':
        return jsonify({'error': 'Cannot respond to a closed ticket'}), 400
    
    # Create response
    response = TicketResponse(
        ticket_id=ticket.id,
        user_id=current_user_id,
        message=data['message'],
        is_from_admin=False
    )
    
    # Update ticket updated_at timestamp
    ticket.updated_at = datetime.utcnow()
    
    db.session.add(response)
    db.session.commit()
    
    return jsonify({
        'message': 'Response added successfully',
        'response_id': response.id
    }), 201

# Close a ticket
@support_bp.route('/tickets/<int:ticket_id>/close', methods=['PUT'])
@jwt_required()
def close_ticket(ticket_id):
    current_user_id = get_jwt_identity()
    
    # Get the ticket
    ticket = SupportTicket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket not found'}), 404
    
    # Check if ticket belongs to current user
    if ticket.user_id != current_user_id:
        return jsonify({'error': 'Unauthorized access to ticket'}), 403
    
    # Check if ticket is already closed
    if ticket.status == 'closed':
        return jsonify({'error': 'Ticket is already closed'}), 400
    
    # Close the ticket
    ticket.status = 'closed'
    ticket.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Ticket closed successfully'
    }), 200

# Admin routes for support tickets

# Get all tickets (admin)
@support_bp.route('/admin/tickets', methods=['GET'])
@admin_required
def admin_get_tickets():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')  # 'open', 'closed', 'all'
    category = request.args.get('category')
    
    query = SupportTicket.query
    
    # Filter by status if provided
    if status == 'open':
        query = query.filter_by(status='open')
    elif status == 'closed':
        query = query.filter_by(status='closed')
    
    # Filter by category if provided
    if category:
        query = query.filter_by(category=category)
    
    tickets = query.order_by(desc(SupportTicket.updated_at))\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for ticket in tickets.items:
        # Get user info
        user = User.query.get(ticket.user_id)
        
        # Count responses
        response_count = TicketResponse.query.filter_by(ticket_id=ticket.id).count()
        
        # Check if admin has responded
        admin_responded = TicketResponse.query\
            .filter_by(ticket_id=ticket.id, is_from_admin=True)\
            .first() is not None
        
        result.append({
            'id': ticket.id,
            'subject': ticket.subject,
            'category': ticket.category,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat(),
            'response_count': response_count,
            'admin_responded': admin_responded,
            'user': {
                'id': user.id,
                'username': user.username,
                'name': f"{user.first_name} {user.last_name}"
            }
        })
    
    return jsonify({
        'tickets': result,
        'total': tickets.total,
        'pages': tickets.pages,
        'current_page': page
    }), 200

# Get ticket categories (admin)
@support_bp.route('/admin/categories', methods=['GET'])
@admin_required
def get_categories():
    # Get distinct categories from tickets
    categories = db.session.query(SupportTicket.category)\
        .distinct()\
        .all()
    
    # Extract category names from result tuples
    category_list = [category[0] for category in categories if category[0]]
    
    return jsonify({'categories': category_list}), 200

# Get a specific ticket with responses (admin)
@support_bp.route('/admin/tickets/<int:ticket_id>', methods=['GET'])
@admin_required
def admin_get_ticket(ticket_id):
    # Get the ticket
    ticket = SupportTicket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket not found'}), 404
    
    # Get user info
    user = User.query.get(ticket.user_id)
    
    # Get ticket responses
    responses = TicketResponse.query\
        .filter_by(ticket_id=ticket.id)\
        .order_by(TicketResponse.created_at)\
        .all()
    
    response_list = []
    for resp in responses:
        # Get user info for response
        resp_user = User.query.get(resp.user_id)
        
        response_list.append({
            'id': resp.id,
            'message': resp.message,
            'created_at': resp.created_at.isoformat(),
            'is_from_admin': resp.is_from_admin,
            'user': {
                'id': resp_user.id,
                'name': f"{resp_user.first_name} {resp_user.last_name}",
                'is_admin': resp_user.is_admin
            }
        })
    
    return jsonify({
        'ticket': {
            'id': ticket.id,
            'subject': ticket.subject,
            'category': ticket.category,
            'status': ticket.status,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat(),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'name': f"{user.first_name} {user.last_name}"
            }
        },
        'responses': response_list
    }), 200

# Admin respond to a ticket
@support_bp.route('/admin/tickets/<int:ticket_id>/respond', methods=['POST'])
@admin_required
def admin_respond_to_ticket(ticket_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate message
    if 'message' not in data or not data['message'].strip():
        return jsonify({'error': 'Message is required'}), 400
    
    # Get the ticket
    ticket = SupportTicket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket not found'}), 404
    
    # Check if ticket is open
    if ticket.status != 'open':
        return jsonify({'error': 'Cannot respond to a closed ticket'}), 400
    
    # Create response
    response = TicketResponse(
        ticket_id=ticket.id,
        user_id=current_user_id,
        message=data['message'],
        is_from_admin=True
    )
    
    # Update ticket updated_at timestamp
    ticket.updated_at = datetime.utcnow()
    
    db.session.add(response)
    db.session.commit()
    
    return jsonify({
        'message': 'Response added successfully',
        'response_id': response.id
    }), 201

# Admin update ticket status
@support_bp.route('/admin/tickets/<int:ticket_id>/status', methods=['PUT'])
@admin_required
def admin_update_ticket_status(ticket_id):
    data = request.get_json()
    
    # Validate status
    if 'status' not in data or data['status'] not in ['open', 'closed']:
        return jsonify({'error': 'Valid status (open/closed) is required'}), 400
    
    # Get the ticket
    ticket = SupportTicket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket not found'}), 404
    
    # Update ticket status
    ticket.status = data['status']
    ticket.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': f'Ticket status updated to {data["status"]}'
    }), 200