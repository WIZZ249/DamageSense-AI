import os
from functools import wraps

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from .ai_engine import classify_image
from .models import Assessment, User, db

main = Blueprint('main', __name__)


def wants_json_response():
    return request.path in {'/assess', '/history', '/api/history'} or request.accept_mimetypes.accept_json


def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if current_user() is None:
            if wants_json_response():
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('main.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


@main.app_context_processor
def inject_user():
    return {'current_user': current_user()}


@main.route('/')
def index():
    if current_user() is None:
        return redirect(url_for('main.login'))
    return redirect(url_for('main.home'))


@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user() is not None:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'error')
        elif password != confirm_password:
            flash('Passwords do not match.', 'error')
        elif User.query.filter((User.username == username) | (User.email == email)).first():
            flash('An account with that username or email already exists.', 'error')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            session.clear()
            session['user_id'] = user.id
            flash('Account created. Welcome to your workspace.', 'success')
            return redirect(url_for('main.home'))

    return render_template('register.html')


@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user() is not None:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        identity = request.form.get('identity', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter((User.username == identity) | (User.email == identity.lower())).first()

        if user and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            return redirect(request.args.get('next') or url_for('main.home'))

        flash('Invalid username, email, or password.', 'error')

    return render_template('login.html')


@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


@main.route('/home')
@login_required
def home():
    user = current_user()
    reports = Assessment.query.filter_by(user_id=user.id).order_by(Assessment.id.desc()).limit(50).all()
    return render_template('upload.html', reports=reports, reports_json=[report.to_dict() for report in reports])


@main.route('/upload', methods=['GET', 'POST'])
@main.route('/assess', methods=['POST'])
@login_required
def upload():
    if request.method == 'GET':
        return redirect(url_for('main.home'))

    file = request.files.get('image') or request.files.get('file')

    if file is None:
        if wants_json_response():
            return jsonify({'error': 'No file provided'}), 400
        return redirect(url_for('main.home'))

    if file.filename == '':
        if wants_json_response():
            return jsonify({'error': 'Empty filename'}), 400
        return redirect(url_for('main.home'))

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
        user_id=current_user().id,
        filename=filename,
        label=label,
        confidence=confidence,
        severity=severity,
    )
    db.session.add(new_report)
    db.session.commit()

    if wants_json_response():
        return jsonify(new_report.to_dict())

    return redirect(url_for('main.home'))


@main.route('/history')
@main.route('/api/history')
@login_required
def api_history():
    records = Assessment.query.filter_by(user_id=current_user().id).order_by(Assessment.id.desc()).limit(50).all()
    return jsonify([record.to_dict() for record in records])


@main.route('/health')
def health():
    return jsonify({'status': 'ok'})
