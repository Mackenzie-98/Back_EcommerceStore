from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

from app.config import Config, DevelopmentConfig
from app.extensions import db, redis_client, ma
from app.api.v1 import api_v1_bp
from app.api.middleware.error_handler import register_error_handlers


def create_app(config_class=DevelopmentConfig):
    """Application factory pattern for Flask app creation"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    ma.init_app(app)
    
    # JWT Configuration
    jwt = JWTManager(app)
    
    # CORS Configuration
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Rate Limiting
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=app.config['REDIS_URL']
    )
    limiter.init_app(app)
    
    # Database Migrations
    Migrate(app, db)
    
    # Initialize Redis
    redis_client.init_app(app)
    
    # Initialize ElasticSearch (commented out for now)
    # es_client.init_app(app)
    
    # Initialize Celery (commented out for now)
    # celery.init_app(app)
    
    # Register blueprints
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    
    # Register error handlers
    register_error_handlers(app)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring"""
        try:
            # Check database connection
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"
        
        try:
            # Check Redis connection
            redis_client.ping()
            redis_status = "healthy"
        except Exception:
            redis_status = "unhealthy"
        
        # ElasticSearch check commented out for now
        # try:
        #     # Check ElasticSearch connection
        #     es_client.ping()
        #     es_status = "healthy"
        # except Exception:
        #     es_status = "unhealthy"
        es_status = "disabled"
        
        overall_status = "healthy" if all([
            db_status == "healthy",
            redis_status == "healthy",
            # es_status == "healthy"  # Commented out for now
        ]) else "unhealthy"
        
        return {
            "status": overall_status,
            "services": {
                "database": db_status,
                "redis": redis_status,
                "elasticsearch": es_status
            }
        }
    
    return app 