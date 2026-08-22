import os

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import inspect, text


db = SQLAlchemy()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# Columns added after the original schema. Listed here so an already-deployed
# SQLite database gets them added in place (ALTER TABLE ... ADD COLUMN) rather
# than failing with "no such column" — this never drops or rewrites existing
# data, it only adds new nullable columns.
_ASSESSMENT_COLUMN_ADDITIONS = {
    'urgency': 'VARCHAR(20)',
    'recommendation_summary': 'VARCHAR(255)',
    'recommendation_next_step': 'TEXT',
}


def migrate_legacy_sqlite_schema(app):
    """Non-destructively bring an existing SQLite schema up to date."""
    if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        return

    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
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

    with app.app_context():
        db.create_all()
        migrate_legacy_sqlite_schema(app)

    return app
