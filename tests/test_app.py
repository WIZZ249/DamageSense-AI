import io

import pytest
from PIL import Image

from app import create_app, db


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
    assert data['filename'] == 'building.png'
    assert data['label']
    assert data['severity'] in {'CRITICAL', 'STABLE', 'UNKNOWN'}


def test_history_is_scoped_to_logged_in_user(client):
    """Each user should only see their own uploads."""
    register(client, username='alpha', email='alpha@example.com')
    client.post('/assess', data=make_image_upload('alpha.png'), content_type='multipart/form-data')
    alpha_history = client.get('/history').get_json()
    assert len(alpha_history) == 1
    assert alpha_history[0]['filename'] == 'alpha.png'

    client.get('/logout')
    register(client, username='beta', email='beta@example.com')
    beta_history = client.get('/history').get_json()
    assert beta_history == []
