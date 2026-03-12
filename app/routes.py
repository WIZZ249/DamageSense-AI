from flask import Blueprint, request, jsonify, render_template, current_app
from app import db
from app.models import Assessment
from app.ai_engine import classify_image
import os

main = Blueprint('main', __name__)

@main.route('/')
def index():
    """Serve the main dashboard."""
    return render_template('upload.html')

@main.route('/assess', methods=['POST'])
def assess():
    """
    Accepts an image upload, runs AI classification,
    saves result to database, returns JSON.
    """
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed:
        return jsonify({'error': f'File type .{ext} not allowed'}), 400

    file_bytes = file.read()

    try:
        result = classify_image(file_bytes)
    except Exception as e:
        return jsonify({'error': f'AI classification failed: {str(e)}'}), 500

    # Save to database
    record = Assessment(
        filename=file.filename,
        label=result['label'],
        confidence=result['confidence'],
        severity=result['severity']
    )
    db.session.add(record)
    db.session.commit()

    return jsonify(record.to_dict()), 200

@main.route('/history')
def history():
    """Return all past assessments as JSON."""
    records = Assessment.query.order_by(Assessment.timestamp.desc()).limit(50).all()
    return jsonify([r.to_dict() for r in records])

@main.route('/health')
def health():
    """Health check endpoint for deployment."""
    return jsonify({'status': 'ok', 'service': 'DamageSense AI'}), 200