import csv
import hashlib
import io
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from . import limiter
from .ai_engine import classify_image
from .email_service import email_enabled, send_password_reset_email, send_registration_email
from .models import Assessment, AuditLog, User, db

main = Blueprint('main', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
MIN_PASSWORD_LENGTH = 8
RESET_TOKEN_TTL = timedelta(hours=1)


def record_audit(action, actor=None, target=None, metadata=None):
    """Persist an operational event without allowing logging failures to break requests."""
    try:
        db.session.add(AuditLog(
            action=action,
            actor_user_id=actor.id if actor else None,
            target_user_id=target.id if target else None,
            metadata_json=json.dumps(metadata or {}, sort_keys=True),
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr),
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Could not write audit event: %s', action)


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
            record_audit('user_registered', target=user)
            send_registration_email(user)
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
            record_audit('login_success', actor=user)
            session.clear()
            session['user_id'] = user.id
            return redirect(request.args.get('next') or (url_for('main.admin') if user.is_admin else url_for('main.home')))

        record_audit('login_failed', metadata={'identity_provided': bool(identity)})
        flash('Invalid username, email, or password.', 'error')

    return render_template('login.html')


@main.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit('5 per hour')
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first() if email else None
        if user and user.is_active:
            raw_token = secrets.token_urlsafe(32)
            user.reset_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            user.reset_token_expires_at = datetime.utcnow() + RESET_TOKEN_TTL
            db.session.commit()
            reset_url = url_for('main.reset_password', token=raw_token, _external=True)
            send_password_reset_email(user, reset_url)
            record_audit('password_reset_requested', target=user)
        else:
            record_audit('password_reset_requested_unknown')
        flash('If an active account matches that email, a password reset link has been sent.', 'success')
        return redirect(url_for('main.forgot_password'))
    return render_template('forgot_password.html')


@main.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit('10 per hour')
def reset_password(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user = User.query.filter_by(reset_token_hash=token_hash).first()
    is_valid = bool(user and user.is_active and user.reset_token_expires_at and user.reset_token_expires_at > datetime.utcnow())
    if not is_valid:
        return render_template('error.html', code=400, title='Reset link expired', message='This password reset link is invalid or has expired. Request a new link to continue.'), 400
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.', 'error')
        elif password != confirm_password:
            flash('Passwords do not match.', 'error')
        else:
            user.set_password(password)
            user.reset_token_hash = None
            user.reset_token_expires_at = None
            db.session.commit()
            record_audit('password_reset_completed', target=user)
            flash('Password updated. You can now log in.', 'success')
            return redirect(url_for('main.login'))
    return render_template('reset_password.html', token=token)


@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


@main.route('/admin')
@admin_required
def admin():
    users = User.query.order_by(User.created_at.desc(), User.id.desc()).all()
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    today = datetime.utcnow().date()
    activity = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        activity.append({'label': day.strftime('%b %d'), 'count': Assessment.query.filter(Assessment.timestamp >= start, Assessment.timestamp < end).count()})
    return render_template(
        'admin.html',
        users=users,
        total_users=User.query.count(),
        active_users=User.query.filter_by(is_active=True).count(),
        admin_users=User.query.filter_by(role='admin').count(),
        total_assessments=Assessment.query.count(),
        critical_assessments=Assessment.query.filter_by(severity='CRITICAL').count(),
        recent_logs=recent_logs,
        activity=activity,
        email_enabled=email_enabled(),
    )


def assessment_export_rows():
    assessments = Assessment.query.join(User, Assessment.user_id == User.id).order_by(Assessment.timestamp.desc(), Assessment.id.desc()).all()
    return [[
        report.timestamp.strftime('%Y-%m-%d %H:%M:%S'), report.user.username, report.user.email,
        report.filename, report.label, f'{report.confidence:.2f}%', report.severity,
        report.urgency or '', report.recommendation_summary or '', report.recommendation_next_step or '',
    ] for report in assessments]


@main.route('/admin/exports/assessments.csv')
@admin_required
def export_assessments_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'Username', 'Email', 'Filename', 'Classification', 'Confidence', 'Severity', 'Urgency', 'Recommendation', 'Next step'])
    writer.writerows(assessment_export_rows())
    record_audit('assessment_exported', actor=current_user(), metadata={'format': 'csv'})
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=damagesense-assessments.csv'})


@main.route('/admin/exports/assessments.pdf')
@admin_required
def export_assessments_pdf():
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    rows = [['Date', 'User', 'Classification', 'Confidence', 'Severity', 'Recommendation']]
    for row in assessment_export_rows():
        rows.append([row[0], row[1], row[4], row[5], row[6], row[8] or '-'])
    story = [Paragraph('DamageSense AI — Assessment Report', styles['Title']), Spacer(1, 10), Paragraph(f'Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")} · {len(rows) - 1} assessments across all users', styles['Normal']), Spacer(1, 14)]
    table = Table(rows, repeatRows=1, colWidths=[75, 70, 85, 55, 55, 155])
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#122640')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 7), ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#c9d3df')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f7fb')])]))
    story.append(table)
    document.build(story)
    record_audit('assessment_exported', actor=current_user(), metadata={'format': 'pdf'})
    buffer.seek(0)
    return Response(buffer.read(), mimetype='application/pdf', headers={'Content-Disposition': 'attachment; filename=damagesense-assessments.pdf'})


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
        record_audit('user_status_changed', actor=actor, target=target, metadata={'is_active': target.is_active})
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
        record_audit('user_role_changed', actor=actor, target=target, metadata={'role': target.role})
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
    record_audit('assessment_created', actor=current_user(), target=current_user(), metadata={'assessment_id': new_report.id, 'severity': severity, 'label': label})
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
