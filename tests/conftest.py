import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('CREATE_DB', '1')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402


@pytest.fixture()
def app():
    application = create_app()
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SERVER_NAME='localhost',
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def registered_user(client):
    """Register a fresh user and return their credentials."""
    unique = uuid.uuid4().hex[:10]
    email = f"{unique}@example.com"
    password = "pass1234"
    client.post(
        '/register',
        data={'username': f"user{unique}", 'email': email, 'password': password},
    )
    return {'email': email, 'password': password}


@pytest.fixture()
def logged_in_client(client, registered_user):
    """A test client already logged in (registration logs the user in too)."""
    return client
