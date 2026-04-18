import os
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from .models import Assessment, db
from .ai_engine import analyze_image

bp = Blueprint('main', __name__)

UPLOAD_FOLDER = 'app/static/uploads'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@bp.route('/')
def index():
    reports = Assessment.query.order_by(Assessment.id.desc()).all()
    return render_template('upload.html', reports=reports)


@bp.route('/upload', methods=['GET', 'POST'])
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

            object_name = "AI Processing Error"
            conf_score = "0%"

            try:
                object_name, conf_score = analyze_image(filepath)
            except Exception as e:
                print(f"AI Error: {e}")

            new_report = Assessment(
                filename=filename,
                status=object_name,
                confidence=conf_score
            )
            db.session.add(new_report)
            db.session.commit()

            # Return JSON for Android app, redirect for browser
            if request.accept_mimetypes.accept_json:
                conf_value = float(conf_score.replace('%', '')) if conf_score else 0
                return jsonify({
                    "id": new_report.id,
                    "filename": filename,
                    "label": object_name,
                    "confidence": conf_value,
                    "severity": "CRITICAL" if conf_value < 60 else "STABLE",
                    "timestamp": str(new_report.id)
                })

            return redirect(url_for('main.index'))

    return render_template('upload.html')


@bp.route('/api/history')
def api_history():
    records = Assessment.query.order_by(Assessment.id.desc()).limit(50).all()
    return jsonify([
        {
            "id": r.id,
            "filename": r.filename,
            "label": r.status,
            "confidence": float(r.confidence.replace('%', '')) if r.confidence else 0,
            "severity": "CRITICAL" if float(r.confidence.replace('%', '') or 0) < 60 else "STABLE",
            "timestamp": str(r.id)
        }
        for r in records
    ])


@bp.route('/health')
def health():
    return jsonify({"status": "ok"})
