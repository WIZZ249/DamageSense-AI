import pytest

from app import create_app, db
from app.models import User


@pytest.fixture
def verification_client(tmp_path, monkeypatch):
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'verification.db'}",
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'WTF_CSRF_ENABLED': False,
        'REQUIRE_EMAIL_VERIFICATION': True,
    })
    with app.app_context():
        user = User(username='unverified', email='unverified@example.com', email_verified=False)
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
    monkeypatch.setattr('app.verification.email_enabled', lambda: True)
    with app.test_client() as client:
        yield client


def test_resend_verification_generates_fresh_token(verification_client, monkeypatch):
    sent = {}

    def capture_email(user, verification_url):
        sent['url'] = verification_url
        return True

    monkeypatch.setattr('app.verification.send_email_verification_email', capture_email)
    response = verification_client.post(
        '/resend-verification',
        data={'email': 'unverified@example.com'},
    )
    assert response.status_code == 200
    assert b'new verification email has been sent' in response.data
    assert sent['url'].startswith('http')

    with verification_client.application.app_context():
        user = User.query.filter_by(email='unverified@example.com').first()
        assert user.email_verified is False
        assert user.verification_token_hash
        assert user.verification_token_expires_at


def test_unverified_user_cannot_login_until_verified(verification_client):
    response = verification_client.post('/login', data={
        'identity': 'unverified@example.com',
        'password': 'password123',
    })
    assert response.status_code == 200
    assert b'Please verify your email address before signing in.' in response.data
