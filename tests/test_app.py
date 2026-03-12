import pytest
from app import create_app, db

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

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