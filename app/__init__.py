import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import inspect, text
from dotenv import load_dotenv

load_dotenv()

from app.models import db, User
from app.config import Config
from app.utils.strings import get_string, translate_name
from app.utils.icons import display_item_name, icon_choices, render_item_icon

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

def _ensure_auth_schema(app):
    inspector = inspect(db.engine)
    if not inspector.has_table('user'):
        return

    existing_columns = {column['name'] for column in inspector.get_columns('user')}
    quote = db.engine.dialect.identifier_preparer.quote
    user_table = quote('user')

    with db.engine.begin() as conn:
        if 'email' not in existing_columns:
            conn.execute(text(f'ALTER TABLE {user_table} ADD COLUMN email VARCHAR(120)'))
        if 'email_verified' not in existing_columns:
            default_value = '0' if db.engine.dialect.name == 'sqlite' else 'FALSE'
            conn.execute(text(
                f'ALTER TABLE {user_table} ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT {default_value}'
            ))

        if db.engine.dialect.name in ('sqlite', 'postgresql'):
            index_name = quote('ix_user_email_unique')
            conn.execute(text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} '
                f'ON {user_table} (email) WHERE email IS NOT NULL'
            ))

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
        return dict(
            get_string=get_string,
            translate_name=translate_name,
            csrf_token=generate_csrf,
            display_item_name=display_item_name,
            icon_choices=icon_choices,
            render_item_icon=render_item_icon,
        )

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
        _ensure_auth_schema(app)

    return app
