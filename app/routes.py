import os
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from .models import Assessment, db
from .ai_engine import classify_image

main = Blueprint('main', __name__)

UPLOAD_FOLDER = 'app/static/uploads'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@main.route('/')
def index():
    reports = Assessment.query.order_by(Assessment.id.desc()).all()
    return render_template('upload.html', reports=reports)


@main.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            if request.accept_mimetypes.accept_json:
                return jsonify({"error": "No file provided"}), 400
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            if request.accept_mimetypes.accept_json:
                return jsonify({"error": "Empty filename"}), 400
            return redirect(request.url)

        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            label = "analysis_error"
            confidence = 0.0
            severity = "UNKNOWN"

            try:
                file_bytes = open(filepath, 'rb').read()
                result = classify_image(file_bytes)
                label = result['label']
                confidence = result['confidence']
                severity = result['severity']
            except Exception as e:
                print(f"AI Error: {e}")

            new_report = Assessment(
                filename=filename,
                status=label,
                confidence=str(confidence)
            )
            db.session.add(new_report)
            db.session.commit()

            if request.accept_mimetypes.accept_json:
                return jsonify({
                    "id": new_report.id,
                    "filename": filename,
                    "label": label,
                    "confidence": confidence,
                    "severity": severity,
                    "timestamp": str(new_report.id)
                })

            return redirect(url_for('main.index'))

    return render_template('upload.html')


@main.route('/api/history')
def api_history():
    records = Assessment.query.order_by(Assessment.id.desc()).limit(50).all()
    return jsonify([
        {
            "id": r.id,
            "filename": r.filename,
            "label": r.status,
            "confidence": float(r.confidence) if r.confidence else 0,
            "severity": "CRITICAL" if float(r.confidence or 0) < 60 else "STABLE",
            "timestamp": str(r.id)
        }
        for r in records
    ])


@main.route('/health')
def health():
    return jsonify({"status": "ok"})
