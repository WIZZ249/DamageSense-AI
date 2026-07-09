import os

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from .ai_engine import classify_image
from .models import Assessment, db

main = Blueprint('main', __name__)


def wants_json_response():
    return request.path == '/assess' or request.accept_mimetypes.accept_json


@main.route('/')
def index():
    reports = Assessment.query.order_by(Assessment.id.desc()).all()
    return render_template('upload.html', reports=reports)


@main.route('/upload', methods=['GET', 'POST'])
@main.route('/assess', methods=['POST'])
def upload():
    if request.method == 'POST':
        file = request.files.get('image') or request.files.get('file')

        if file is None:
            if wants_json_response():
                return jsonify({'error': 'No file provided'}), 400
            return redirect(request.url)

        if file.filename == '':
            if wants_json_response():
                return jsonify({'error': 'Empty filename'}), 400
            return redirect(request.url)

        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        label = 'analysis_error'
        confidence = 0.0
        severity = 'UNKNOWN'

        try:
            with open(filepath, 'rb') as uploaded_file:
                result = classify_image(uploaded_file.read())
            label = result['label']
            confidence = result['confidence']
            severity = result['severity']
        except Exception as exc:
            current_app.logger.exception('AI Error: %s', exc)

        new_report = Assessment(
            filename=filename,
            label=label,
            confidence=confidence,
            severity=severity,
        )
        db.session.add(new_report)
        db.session.commit()

        if wants_json_response():
            return jsonify(new_report.to_dict())

        return redirect(url_for('main.index'))

    return render_template('upload.html')


@main.route('/history')
@main.route('/api/history')
def api_history():
    records = Assessment.query.order_by(Assessment.id.desc()).limit(50).all()
    return jsonify([record.to_dict() for record in records])


@main.route('/health')
def health():
    return jsonify({'status': 'ok'})
