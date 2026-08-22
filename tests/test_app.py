import io

import pytest
from PIL import Image

from app import create_app, db
from app.models import User


@pytest.fixture
def client(tmp_path):
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'WTF_CSRF_ENABLED': False,
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()


def register(client, username='field_user', email='field@example.com', password='password123'):
    return client.post('/register', data={
        'username': username,
        'email': email,
        'password': password,
        'confirm_password': password,
    }, follow_redirects=True)


def make_image_upload(filename='building.png'):
    image = Image.new('RGB', (16, 16), color='white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return {'image': (buffer, filename)}


def test_health_check(client):
    """Health endpoint should return 200."""
    r = client.get('/health')
    assert r.status_code == 200
    assert b'ok' in r.data


def test_index_redirects_to_login(client):
    """Anonymous users should start at login."""
    r = client.get('/')
    assert r.status_code == 302
    assert '/login' in r.headers['Location']


def test_register_creates_user_home(client):
    """Registration should create a logged-in workspace."""
    r = register(client)
    assert r.status_code == 200
    assert b"field_user's Assessment Home" in r.data


def test_assess_requires_login(client):
    """Uploads should require authentication."""
    r = client.post('/assess')
    assert r.status_code == 401
    assert r.get_json()['error'] == 'Authentication required'


def test_assess_no_file(client):
    """Assess endpoint should reject empty requests for logged-in users."""
    register(client)
    r = client.post('/assess')
    assert r.status_code == 400
    assert r.get_json()['error'] == 'No file provided'


def test_assess_upload_creates_report(client):
    """Assess endpoint should analyse an image and return JSON."""
    register(client)
    r = client.post(
        '/assess',
        data=make_image_upload(),
        content_type='multipart/form-data',
    )

    assert r.status_code == 200
    data = r.get_json()
    # Stored filename is now UUID-prefixed to avoid collisions between users;
    # check it preserves the original name as a suffix instead of an exact match.
    assert data['filename'].endswith('building.png')
    assert data['label']
    assert data['severity'] in {'CRITICAL', 'STABLE', 'UNKNOWN'}


def test_history_is_scoped_to_logged_in_user(client):
    """Each user should only see their own uploads."""
    register(client, username='alpha', email='alpha@example.com')
    client.post('/assess', data=make_image_upload('alpha.png'), content_type='multipart/form-data')
    alpha_history = client.get('/history').get_json()
    assert len(alpha_history) == 1
    assert alpha_history[0]['filename'].endswith('alpha.png')

    client.get('/logout')
    register(client, username='beta', email='beta@example.com')
    beta_history = client.get('/history').get_json()
    assert beta_history == []


def make_admin_app(tmp_path, monkeypatch):
    monkeypatch.setenv('ADMIN_USERNAME', 'operations_admin')
    monkeypatch.setenv('ADMIN_EMAIL', 'operations@example.com')
    monkeypatch.setenv('ADMIN_PASSWORD', 'secure-admin-password')
    return create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'admin.db'}",
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'WTF_CSRF_ENABLED': False,
    })


def test_configured_admin_is_provisioned_and_redirects_to_console(tmp_path, monkeypatch):
    """Render environment variables should create a working administrator account."""
    app = make_admin_app(tmp_path, monkeypatch)
    with app.app_context():
        admin = User.query.filter_by(email='operations@example.com').first()
        assert admin is not None
        assert admin.is_admin is True
        assert admin.is_active is True
        assert admin.check_password('secure-admin-password')
    with app.test_client() as admin_client:
        response = admin_client.post('/login', data={
            'identity': 'operations_admin',
            'password': 'secure-admin-password',
        })
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/admin')
        assert admin_client.get('/admin').status_code == 200


def test_standard_user_cannot_access_admin_console(client):
    """The admin console must reject authenticated standard users."""
    register(client)
    response = client.get('/admin')
    assert response.status_code == 403
    assert b'Admin access required' in response.data


def test_admin_can_toggle_user_status_and_role_but_not_self(tmp_path, monkeypatch):
    """Admins can manage other users while self-protection remains enforced."""
    app = make_admin_app(tmp_path, monkeypatch)
    with app.app_context():
        other = User(username='other_user', email='other@example.com')
        other.set_password('password123')
        db.session.add(other)
        db.session.commit()
        other_id = other.id
        admin_id = User.query.filter_by(username='operations_admin').first().id

    with app.test_client() as admin_client:
        admin_client.post('/login', data={'identity': 'operations_admin', 'password': 'secure-admin-password'})
        assert admin_client.post(f'/admin/users/{other_id}/toggle-role').status_code == 302
        assert admin_client.post(f'/admin/users/{other_id}/toggle-active').status_code == 302
        with app.app_context():
            other = db.session.get(User, other_id)
            assert other.is_admin is True
            assert other.is_active is False
        admin_client.post(f'/admin/users/{admin_id}/toggle-active')
        admin_client.post(f'/admin/users/{admin_id}/toggle-role')
        with app.app_context():
            admin = db.session.get(User, admin_id)
            assert admin.is_admin is True
            assert admin.is_active is True
