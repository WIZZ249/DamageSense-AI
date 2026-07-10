import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect


db = SQLAlchemy()


def reset_legacy_sqlite_schema(app):
    """Recreate old SQLite databases that predate user-owned assessments."""
    if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        return

    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    if 'assessments' not in table_names:
        return

    assessment_columns = {column['name'] for column in inspector.get_columns('assessments')}
    if 'user_id' in assessment_columns and 'users' in table_names:
        return

    db.drop_all()
    db.create_all()


def create_app(config=None):
    app = Flask(__name__, template_folder='../templates', static_folder='static')
    app.config.update(
        SECRET_KEY=os.getenv('FLASK_SECRET_KEY', 'dev'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///damagesense.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.getenv('UPLOAD_FOLDER', 'app/static/uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )

    if config:
        app.config.update(config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        reset_legacy_sqlite_schema(app)

    return app
