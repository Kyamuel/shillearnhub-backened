from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import desc
import os
from werkzeug.utils import secure_filename

from models import db, BlogPost, User
from ..admin.routes import admin_required

blog_bp = Blueprint('blog', __name__)

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

# Get all blog posts (public)
@blog_bp.route('/', methods=['GET'])
def get_blog_posts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    category = request.args.get('category')
    
    query = BlogPost.query.filter_by(is_published=True)
    
    # Filter by category if provided
    if category:
        query = query.filter_by(category=category)
    
    # Order by published date (newest first)
    posts = query.order_by(desc(BlogPost.published_at))\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for post in posts.items:
        author = User.query.get(post.author_id)
        result.append({
            'id': post.id,
            'title': post.title,
            'slug': post.slug,
            'summary': post.summary,
            'featured_image': post.featured_image,
            'category': post.category,
            'published_at': post.published_at.isoformat(),
            'author': {
                'id': author.id,
                'name': f"{author.first_name} {author.last_name}",
                'profile_picture': author.profile_picture
            }
        })
    
    return jsonify({
        'posts': result,
        'total': posts.total,
        'pages': posts.pages,
        'current_page': page
    }), 200

# Get a single blog post by slug (public)
@blog_bp.route('/<slug>', methods=['GET'])
def get_blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, is_published=True).first()
    if not post:
        return jsonify({'error': 'Blog post not found'}), 404
    
    author = User.query.get(post.author_id)
    
    return jsonify({
        'id': post.id,
        'title': post.title,
        'slug': post.slug,
        'content': post.content,
        'summary': post.summary,
        'featured_image': post.featured_image,
        'category': post.category,
        'published_at': post.published_at.isoformat(),
        'updated_at': post.updated_at.isoformat(),
        'author': {
            'id': author.id,
            'name': f"{author.first_name} {author.last_name}",
            'profile_picture': author.profile_picture
        }
    }), 200

# Get blog categories (public)
@blog_bp.route('/categories', methods=['GET'])
def get_categories():
    # Get distinct categories from blog posts
    categories = db.session.query(BlogPost.category)\
        .filter(BlogPost.is_published == True)\
        .distinct()\
        .all()
    
    # Extract category names from result tuples
    category_list = [category[0] for category in categories if category[0]]
    
    return jsonify({'categories': category_list}), 200

# Admin routes for blog management

# Get all blog posts (including drafts) - admin only
@blog_bp.route('/admin/posts', methods=['GET'])
@admin_required
def admin_get_posts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')  # 'published' or 'draft'
    
    query = BlogPost.query
    
    # Filter by status if provided
    if status == 'published':
        query = query.filter_by(is_published=True)
    elif status == 'draft':
        query = query.filter_by(is_published=False)
    
    posts = query.order_by(desc(BlogPost.created_at))\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    result = []
    for post in posts.items:
        author = User.query.get(post.author_id)
        result.append({
            'id': post.id,
            'title': post.title,
            'slug': post.slug,
            'summary': post.summary,
            'featured_image': post.featured_image,
            'category': post.category,
            'is_published': post.is_published,
            'created_at': post.created_at.isoformat(),
            'published_at': post.published_at.isoformat() if post.published_at else None,
            'updated_at': post.updated_at.isoformat(),
            'author': {
                'id': author.id,
                'name': f"{author.first_name} {author.last_name}"
            }
        })
    
    return jsonify({
        'posts': result,
        'total': posts.total,
        'pages': posts.pages,
        'current_page': page
    }), 200

# Create a new blog post - admin only
@blog_bp.route('/admin/posts', methods=['POST'])
@admin_required
def create_post():
    data = request.form
    
    # Validate required fields
    required_fields = ['title', 'slug', 'content', 'summary', 'category']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Check if slug already exists
    existing_post = BlogPost.query.filter_by(slug=data['slug']).first()
    if existing_post:
        return jsonify({'error': 'A post with this slug already exists'}), 400
    
    # Handle featured image upload
    featured_image = None
    if 'featured_image' in request.files:
        file = request.files['featured_image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Create a unique filename to avoid overwriting
            unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
            # Save file to upload folder
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'blog', unique_filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            featured_image = f"/uploads/blog/{unique_filename}"
    
    # Get current user as author
    current_user_id = get_jwt_identity()
    
    # Create new blog post
    post = BlogPost(
        title=data['title'],
        slug=data['slug'],
        content=data['content'],
        summary=data['summary'],
        featured_image=featured_image,
        category=data['category'],
        author_id=current_user_id,
        is_published=data.get('is_published', 'false').lower() == 'true'
    )
    
    # Set published_at if post is being published
    if post.is_published:
        post.published_at = datetime.utcnow()
    
    db.session.add(post)
    db.session.commit()
    
    return jsonify({
        'message': 'Blog post created successfully',
        'post_id': post.id,
        'slug': post.slug
    }), 201

# Update an existing blog post - admin only
@blog_bp.route('/admin/posts/<int:post_id>', methods=['PUT'])
@admin_required
def update_post(post_id):
    post = BlogPost.query.get(post_id)
    if not post:
        return jsonify({'error': 'Blog post not found'}), 404
    
    data = request.form
    
    # Update post fields
    if 'title' in data:
        post.title = data['title']
    
    if 'slug' in data:
        # Check if slug already exists on another post
        existing_post = BlogPost.query.filter_by(slug=data['slug']).first()
        if existing_post and existing_post.id != post.id:
            return jsonify({'error': 'Another post with this slug already exists'}), 400
        post.slug = data['slug']
    
    if 'content' in data:
        post.content = data['content']
    
    if 'summary' in data:
        post.summary = data['summary']
    
    if 'category' in data:
        post.category = data['category']
    
    # Handle featured image upload
    if 'featured_image' in request.files:
        file = request.files['featured_image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Create a unique filename to avoid overwriting
            unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
            # Save file to upload folder
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'blog', unique_filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            
            # Delete old image if exists (optional)
            # if post.featured_image and os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], post.featured_image.lstrip('/'))):
            #     os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], post.featured_image.lstrip('/')))
            
            post.featured_image = f"/uploads/blog/{unique_filename}"
    
    # Handle publishing status change
    if 'is_published' in data:
        is_published = data.get('is_published', 'false').lower() == 'true'
        
        # If post is being published for the first time
        if is_published and not post.is_published:
            post.published_at = datetime.utcnow()
        
        post.is_published = is_published
    
    post.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'message': 'Blog post updated successfully',
        'post_id': post.id
    }), 200

# Delete a blog post - admin only
@blog_bp.route('/admin/posts/<int:post_id>', methods=['DELETE'])
@admin_required
def delete_post(post_id):
    post = BlogPost.query.get(post_id)
    if not post:
        return jsonify({'error': 'Blog post not found'}), 404
    
    # Delete featured image file (optional)
    # if post.featured_image and os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], post.featured_image.lstrip('/'))):
    #     os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], post.featured_image.lstrip('/')))
    
    db.session.delete(post)
    db.session.commit()
    
    return jsonify({
        'message': 'Blog post deleted successfully'
    }), 200