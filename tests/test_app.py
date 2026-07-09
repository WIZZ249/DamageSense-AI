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
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_health_check(client):
    """Health endpoint should return 200."""
    r = client.get('/health')
    assert r.status_code == 200
    assert b'ok' in r.data


def test_index_loads(client):
    """Home page should load."""
    r = client.get('/')
    assert r.status_code == 200


def test_assess_no_file(client):
    """Assess endpoint should reject empty requests."""
    r = client.post('/assess')
    assert r.status_code == 400
    assert r.get_json()['error'] == 'No file provided'


def test_assess_upload_creates_report(client):
    """Assess endpoint should analyse an image and return JSON."""
    image = Image.new('RGB', (16, 16), color='white')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)

    r = client.post(
        '/assess',
        data={'image': (buffer, 'building.png')},
        content_type='multipart/form-data',
    )

    assert r.status_code == 200
    data = r.get_json()
    assert data['filename'] == 'building.png'
    assert data['label']
    assert data['severity'] in {'CRITICAL', 'STABLE', 'UNKNOWN'}
