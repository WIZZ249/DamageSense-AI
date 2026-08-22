import os
import uuid
from functools import wraps

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from . import limiter
from .ai_engine import classify_image
from .models import Assessment, User, db

main = Blueprint('main', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
MIN_PASSWORD_LENGTH = 8


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
        user = current_user()
        if user is None or not user.is_active:
            session.clear()
            if wants_json_response():
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('main.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = current_user()
        if user is None or not user.is_active:
            session.clear()
            if wants_json_response():
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('main.login', next=request.path))
        if not user.is_admin:
            if wants_json_response():
                return jsonify({'error': 'Administrator access required'}), 403
            return render_template('error.html', code=403, title='Admin access required', message='This area is restricted to administrators.'), 403
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
@limiter.limit('10 per minute')
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
        elif len(password) < MIN_PASSWORD_LENGTH:
            flash(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.', 'error')
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
@limiter.limit('10 per minute')
def login():
    if current_user() is not None:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        identity = request.form.get('identity', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter((User.username == identity) | (User.email == identity.lower())).first()

        if user and user.is_active and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            return redirect(request.args.get('next') or (url_for('main.admin') if user.is_admin else url_for('main.home')))

        flash('Invalid username, email, or password.', 'error')

    return render_template('login.html')


@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


@main.route('/admin')
@admin_required
def admin():
    users = User.query.order_by(User.created_at.desc(), User.id.desc()).all()
    return render_template(
        'admin.html',
        users=users,
        total_users=User.query.count(),
        active_users=User.query.filter_by(is_active=True).count(),
        admin_users=User.query.filter_by(role='admin').count(),
        total_assessments=Assessment.query.count(),
    )


@main.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    target = db.session.get(User, user_id)
    actor = current_user()
    if target is None:
        flash('User not found.', 'error')
    elif target.id == actor.id:
        flash('You cannot deactivate your own administrator account.', 'error')
    else:
        target.is_active = not target.is_active
        db.session.commit()
        flash(f'{target.username} is now {"active" if target.is_active else "disabled"}.', 'success')
    return redirect(url_for('main.admin'))


@main.route('/admin/users/<int:user_id>/toggle-role', methods=['POST'])
@admin_required
def toggle_user_role(user_id):
    target = db.session.get(User, user_id)
    actor = current_user()
    if target is None:
        flash('User not found.', 'error')
    elif target.id == actor.id:
        flash('You cannot change your own administrator role.', 'error')
    elif target.is_admin and User.query.filter_by(role='admin', is_active=True).count() <= 1:
        flash('Keep at least one active administrator account.', 'error')
    else:
        target.role = 'user' if target.is_admin else 'admin'
        db.session.commit()
        flash(f'{target.username} is now an {"administrator" if target.is_admin else "standard user"}.', 'success')
    return redirect(url_for('main.admin'))


@main.route('/home')
@login_required
def home():
    user = current_user()
    reports = Assessment.query.filter_by(user_id=user.id).order_by(Assessment.id.desc()).limit(50).all()
    return render_template('upload.html', reports=reports, reports_json=[report.to_dict() for report in reports])


def _has_allowed_extension(filename):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def _verify_is_image(filepath):
    """Confirm the saved file is actually a decodable image, not just a
    file with an image-like extension."""
    try:
        with Image.open(filepath) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False


@main.route('/upload', methods=['GET', 'POST'])
@main.route('/assess', methods=['POST'])
@login_required
@limiter.limit('30 per minute')
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

    if not _has_allowed_extension(file.filename):
        message = f'Unsupported file type. Allowed: {", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))}'
        if wants_json_response():
            return jsonify({'error': message}), 400
        flash(message, 'error')
        return redirect(url_for('main.home'))

    original_name = secure_filename(file.filename)
    # Prefix with a UUID so concurrent/duplicate filenames across different
    # users (or the same user) never overwrite each other's stored image.
    filename = f'{uuid.uuid4().hex}_{original_name}'
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    if not _verify_is_image(filepath):
        os.remove(filepath)
        message = 'The uploaded file is not a valid image.'
        if wants_json_response():
            return jsonify({'error': message}), 400
        flash(message, 'error')
        return redirect(url_for('main.home'))

    label = 'analysis_error'
    confidence = 0.0
    severity = 'UNKNOWN'
    recommendation = {}

    try:
        with open(filepath, 'rb') as uploaded_file:
            result = classify_image(uploaded_file.read())
        label = result['label']
        confidence = result['confidence']
        severity = result['severity']
        recommendation = result.get('recommendation', {})
    except Exception as exc:
        current_app.logger.exception('AI Error: %s', exc)

    new_report = Assessment(
        user_id=current_user().id,
        filename=filename,
        label=label,
        confidence=confidence,
        severity=severity,
        urgency=recommendation.get('urgency'),
        recommendation_summary=recommendation.get('summary'),
        recommendation_next_step=recommendation.get('next_step'),
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


@main.route('/robots.txt')
def robots_txt():
    return send_from_directory(current_app.root_path + '/..', 'robots.txt')


@main.route('/sitemap.xml')
def sitemap_xml():
    return send_from_directory(current_app.root_path + '/..', 'sitemap.xml')


@main.route('/googleXXXXXXXXXXXXXXXX.html')
def google_site_verification_placeholder():
    """
    Placeholder route for Google Search Console's HTML-file verification
    method. Rename this route (and the return string) to match the exact
    filename Google gives you — e.g. google1a2b3c4d5e6f7g8h.html — and it
    will be served at your domain root, which is what GSC checks for.
    See the deployment guide for the exact steps.
    """
    return Response('google-site-verification: REPLACE-WITH-FILENAME', mimetype='text/html')
