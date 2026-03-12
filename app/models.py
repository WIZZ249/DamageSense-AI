from app import db
from datetime import datetime

class Assessment(db.Model):
    """Stores each structural damage assessment result."""
    __tablename__ = 'assessments'

    id          = db.Column(db.Integer, primary_key=True)
    filename    = db.Column(db.String(255), nullable=False)
    label       = db.Column(db.String(100), nullable=False)
    confidence  = db.Column(db.Float, nullable=False)
    severity    = db.Column(db.String(20), nullable=False)   # CRITICAL / STABLE
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'filename':   self.filename,
            'label':      self.label,
            'confidence': round(self.confidence * 100, 2),
            'severity':   self.severity,
            'timestamp':  self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }