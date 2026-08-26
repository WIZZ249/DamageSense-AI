import logging
import os

import requests

logger = logging.getLogger(__name__)


def email_enabled():
    return bool(os.getenv('SENDGRID_API_KEY') and os.getenv('SENDGRID_FROM_EMAIL'))


def send_transactional_email(to_email, subject, text_content, html_content):
    """Send one transactional email through SendGrid's v3 Mail Send API."""
    api_key = os.getenv('SENDGRID_API_KEY')
    from_email = os.getenv('SENDGRID_FROM_EMAIL')
    if not api_key or not from_email:
        logger.warning('Transactional email skipped because SendGrid is not configured.')
        return False

    payload = {
        'personalizations': [{'to': [{'email': to_email}], 'subject': subject}],
        'from': {'email': from_email, 'name': os.getenv('SENDGRID_FROM_NAME', 'DamageSense AI')},
        'content': [
            {'type': 'text/plain', 'value': text_content},
            {'type': 'text/html', 'value': html_content},
        ],
    }
    try:
        response = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=10,
        )
        if response.status_code not in (200, 202):
            logger.error('SendGrid rejected email with status %s.', response.status_code)
            return False
        return True
    except requests.RequestException:
        logger.exception('SendGrid request failed.')
        return False


def send_registration_email(user):
    name = user.username
    return send_transactional_email(
        user.email,
        'Welcome to DamageSense AI',
        f'Hi {name},\n\nYour DamageSense AI account is ready. Sign in to begin a structural assessment.\n\nRegards,\nDamageSense AI',
        f'<p>Hi {name},</p><p>Your DamageSense AI account is ready. Sign in to begin a structural assessment.</p><p>Regards,<br>DamageSense AI</p>',
    )


def send_password_reset_email(user, reset_url):
    return send_transactional_email(
        user.email,
        'Reset your DamageSense AI password',
        f'We received a request to reset your DamageSense AI password. Use this link within one hour:\n\n{reset_url}\n\nIf you did not request this, you can ignore this email.',
        f'<p>We received a request to reset your DamageSense AI password.</p><p><a href="{reset_url}">Reset your password</a></p><p>This link expires in one hour. If you did not request this, you can ignore this email.</p>',
    )


def send_email_verification_email(user, verification_url):
    return send_transactional_email(
        user.email,
        'Verify your DamageSense AI account',
        f'Hi {user.username},\n\nVerify your DamageSense AI account using this link within 24 hours:\n\n{verification_url}\n\nIf you did not create this account, you can ignore this email.\n\nRegards,\nDamageSense AI',
        f'<p>Hi {user.username},</p><p>Verify your DamageSense AI account using the link below within 24 hours:</p><p><a href="{verification_url}">Verify my email address</a></p><p>If you did not create this account, you can ignore this email.</p><p>Regards,<br>DamageSense AI</p>',
    )
