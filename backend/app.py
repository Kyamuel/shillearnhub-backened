import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_mail import Mail
from celery import Celery

from config import config
from models import db

# Initialize extensions
jwt = JWTManager()
migrate = Migrate()
mail = Mail()

def create_celery_app(app=None):
    app = app or create_app(os.getenv('FLASK_CONFIG') or 'default')
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    CORS(app)
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register blueprints
    from auth.routes import auth_bp
    from user.routes import user_bp
    from mission.routes import mission_bp
    from wallet.routes import wallet_bp
    from admin.routes import admin_bp
    from payment.routes import payment_bp
    from blog.routes import blog_bp
    from support.routes import support_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(mission_bp, url_prefix='/api/missions')
    app.register_blueprint(wallet_bp, url_prefix='/api/wallet')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(payment_bp, url_prefix='/api/payment')
    app.register_blueprint(blog_bp, url_prefix='/api/blog')
    app.register_blueprint(support_bp, url_prefix='/api/support')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500
    
    return app

celery = create_celery_app()