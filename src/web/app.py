"""
Flask application factory for AI Research Assistant.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

from .config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name=None):
    """Create and configure Flask application."""
    
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Import and set up models
    from . import models
    models.db = db
    
    # Register blueprints
    from .blueprints.main import main_bp
    from .blueprints.research import research_bp
    from .blueprints.api import api_bp
    from .blueprints.history import history_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(research_bp, url_prefix='/research')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(history_bp, url_prefix='/history')
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'error': 'Internal server error'}, 500
    
    return app


def create_celery(app):
    """Create Celery instance."""
    from celery import Celery
    
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)