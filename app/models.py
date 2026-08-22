from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(db.Model):
    """Application user with a private assessment workspace."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user', server_default='user')
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assessments = db.relationship('Assessment', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'


class Assessment(db.Model):
    """Stores each structural damage assessment result."""
    __tablename__ = 'assessments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    # Repair-recommendation fields, populated from app/ai_engine.py's
    # REPAIR_RECOMMENDATIONS lookup at assessment time so history rows carry
    # the same guidance the user saw when the assessment was made.
    urgency = db.Column(db.String(20), nullable=True)
    recommendation_summary = db.Column(db.String(255), nullable=True)
    recommendation_next_step = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='assessments')

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'label': self.label,
            'confidence': round(self.confidence, 2),
            'severity': self.severity,
            'urgency': self.urgency,
            'recommendation': {
                'summary': self.recommendation_summary,
                'next_step': self.recommendation_next_step,
            },
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
