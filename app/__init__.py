import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect


db = SQLAlchemy()


def migrate_legacy_sqlite_schema(app):
    """Inspect legacy SQLite schema without ever deleting user data."""
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

    app.config.update(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.getenv('UPLOAD_FOLDER', 'app/static/uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )

    if config:
        app.config.update(config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        migrate_legacy_sqlite_schema(app)

    return app
