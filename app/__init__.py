import os

from flask import Flask, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import inspect, text


db = SQLAlchemy()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# Columns added after the original schema. Listed here so an already-deployed
# database gets them added in place (ALTER TABLE ... ADD COLUMN) rather than
# failing with a missing-column error. This never drops or rewrites existing data.
_USER_COLUMN_ADDITIONS = {
    'role': "VARCHAR(20) NOT NULL DEFAULT 'user'",
    'is_active': 'BOOLEAN NOT NULL DEFAULT TRUE',
    'reset_token_hash': 'VARCHAR(64)',
    'reset_token_expires_at': 'DATETIME',
    # Existing accounts are trusted during migration so this feature does not lock out current users.
    'email_verified': 'BOOLEAN NOT NULL DEFAULT TRUE',
    'verification_token_hash': 'VARCHAR(64)',
    'verification_token_expires_at': 'DATETIME',
}

_ASSESSMENT_COLUMN_ADDITIONS = {
    'urgency': 'VARCHAR(20)',
    'recommendation_summary': 'VARCHAR(255)',
    'recommendation_next_step': 'TEXT',
    'analysis_json': 'TEXT',
    'latitude': 'DOUBLE PRECISION',
    'longitude': 'DOUBLE PRECISION',
    'location_city': 'VARCHAR(120)',
    'location_country': 'VARCHAR(120)',
    'location_source': 'VARCHAR(20)',
}


def migrate_legacy_sqlite_schema(app):
    """Non-destructively bring an existing schema up to date."""

    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    if 'users' in table_names:
        user_columns = {column['name'] for column in inspector.get_columns('users')}
        for column_name, column_type in _USER_COLUMN_ADDITIONS.items():
            if column_name not in user_columns:
                app.logger.info('Adding missing column users.%s', column_name)
                with db.engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE users ADD COLUMN {column_name} {column_type}'))

    if 'assessments' not in table_names:
        return

    assessment_columns = {column['name'] for column in inspector.get_columns('assessments')}
    if 'user_id' not in assessment_columns:
        app.logger.warning(
            'Legacy assessments table detected without user_id. '
            'Skipping destructive migration so existing data is preserved.'
        )
        return

    for column_name, column_type in _ASSESSMENT_COLUMN_ADDITIONS.items():
        if column_name not in assessment_columns:
            app.logger.info('Adding missing column assessments.%s', column_name)
            with db.engine.begin() as connection:
                connection.execute(text(f'ALTER TABLE assessments ADD COLUMN {column_name} {column_type}'))


def provision_admin_from_env(app):
    """Create or promote exactly one configured admin without storing secrets in code."""
    username = os.getenv('ADMIN_USERNAME', '').strip()
    email = os.getenv('ADMIN_EMAIL', '').strip().lower()
    password = os.getenv('ADMIN_PASSWORD', '')
    reset_password = os.getenv('ADMIN_RESET_PASSWORD', '').lower() in {'1', 'true', 'yes'}

    if not any((username, email, password)):
        return
    if not username or not email or not password:
        app.logger.error('ADMIN_USERNAME, ADMIN_EMAIL, and ADMIN_PASSWORD must all be set together.')
        return
    if len(password) < 8:
        app.logger.error('ADMIN_PASSWORD must be at least 8 characters; admin provisioning skipped.')
        return

    from .models import User

    user_by_email = User.query.filter_by(email=email).first()
    user_by_username = User.query.filter_by(username=username).first()
    if user_by_email and user_by_username and user_by_email.id != user_by_username.id:
        app.logger.error('Admin email and username belong to different users; admin provisioning skipped.')
        return

    user = user_by_email or user_by_username
    if user is None:
        user = User(username=username, email=email, role='admin', is_active=True, email_verified=True)
        user.set_password(password)
        db.session.add(user)
        app.logger.info('Provisioned configured admin account: %s', email)
    else:
        user.role = 'admin'
        user.is_active = True
        user.email_verified = True
        if reset_password:
            user.set_password(password)
        app.logger.info('Verified configured admin access for: %s', user.email)
    db.session.commit()


def create_app(config=None):
    app = Flask(__name__, template_folder='../templates', static_folder='static')

    secret_key = os.getenv('FLASK_SECRET_KEY')
    if not secret_key:
        if os.getenv('FLASK_ENV') == 'production':
            raise RuntimeError('FLASK_SECRET_KEY must be configured in production.')
        secret_key = 'development-only-change-me'

    database_url = os.getenv('DATABASE_URL', 'sqlite:///damagesense.db')
    if database_url.startswith('postgres://'):
        database_url = 'postgresql://' + database_url[len('postgres://'):]

    max_upload_mb = int(os.getenv('MAX_UPLOAD_MB', '16'))

    app.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        REQUIRE_EMAIL_VERIFICATION=os.getenv('REQUIRE_EMAIL_VERIFICATION', 'true').lower() in {'1', 'true', 'yes'},
        UPLOAD_FOLDER=os.getenv('UPLOAD_FOLDER', 'app/static/uploads'),
        MAX_CONTENT_LENGTH=max_upload_mb * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        # WTF_CSRF_ENABLED left on by default; tests explicitly disable it.
    )

    if config:
        app.config.update(config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('404.html'), 404

    @app.after_request
    def add_cache_headers(response):
        # CSS/JS must revalidate so production UI changes become visible immediately.
        # Templates use a version query parameter as an additional cache-busting layer.
        if request.path.startswith('/static/'):
            if request.path.endswith(('.css', '.js')):
                response.headers['Cache-Control'] = 'no-cache, must-revalidate'
            else:
                response.headers.setdefault('Cache-Control', 'public, max-age=3600')
        elif request.path.endswith(('.svg', '.ico', '.txt', '.xml')):
            response.headers.setdefault('Cache-Control', 'public, max-age=3600')
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response

    with app.app_context():
        db.create_all()
        migrate_legacy_sqlite_schema(app)
        provision_admin_from_env(app)

    return app
