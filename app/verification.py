import hashlib
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from . import db, limiter
from .email_service import email_enabled, send_email_verification_email
from .models import User

verification = Blueprint('verification', __name__)


@verification.route('/resend-verification', methods=['GET', 'POST'])
@limiter.limit('5 per hour')
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter(func.lower(User.email) == email).first() if email else None

        # Keep the response generic so this endpoint cannot be used to enumerate accounts.
        if user and user.is_active and not user.email_verified:
            if not email_enabled():
                flash('Email verification is temporarily unavailable. Please try again later.', 'error')
                return render_template('resend_verification.html')

            raw_token = secrets.token_urlsafe(32)
            user.verification_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            user.verification_token_expires_at = datetime.utcnow() + timedelta(hours=24)
            db.session.commit()

            verification_url = url_for('main.verify_email', token=raw_token, _external=True)
            if send_email_verification_email(user, verification_url):
                flash('If that account needs verification, a new verification email has been sent.', 'success')
            else:
                db.session.rollback()
                flash('We could not send the verification email right now. Please try again later.', 'error')
        else:
            flash('If that account needs verification, a new verification email has been sent.', 'success')

        return render_template('resend_verification.html')

    return render_template('resend_verification.html')
