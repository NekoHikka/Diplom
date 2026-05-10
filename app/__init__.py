import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv()

from app.models import db, User
from app.config import Config
from app.utils.strings import get_string, translate_name

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

def create_app():
    app = Flask(__name__, 
                template_folder='../templates', 
                static_folder='../static')
    
    app.config.from_object(Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    @app.context_processor
    def inject_functions():
        return dict(get_string=get_string, translate_name=translate_name, csrf_token=generate_csrf)

    @login_manager.user_loader
    def load_user(user_id):
        from app.repositories.user_repository import get_user_by_id
        return get_user_by_id(user_id)

    from app.routes.auth_routes import auth_bp
    from app.routes.budget_routes import budget_bp
    from app.routes.shared_routes import shared_bp
    from app.routes.ai_routes import ai_bp
    from app.routes.integration_routes import integration_bp
    from app.routes.analytics_routes import analytics_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(shared_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(integration_bp)
    app.register_blueprint(analytics_bp)

    with app.app_context():
        db.create_all()

    return app
