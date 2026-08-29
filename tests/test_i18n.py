import pytest
from app import create_app
from extensions import db
from models import User


@pytest.fixture
def app():
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'BABEL_DEFAULT_LOCALE': 'es',
        'BABEL_DEFAULT_TIMEZONE': 'America/Guatemala',
        'LANGUAGES': {
            'es': 'Español',
            'qu': 'K\'iche\'',
            'cak': 'Kaqchikel',
            'qeq': 'Q\'eqchi\''
        }
    }
    app = create_app(test_config)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_config_languages(app):
    """Test that all required languages and babel configurations are present."""
    languages = app.config.get('LANGUAGES', {})
    assert 'es' in languages
    assert 'qu' in languages
    assert 'cak' in languages
    assert 'qeq' in languages
    assert app.config.get('BABEL_DEFAULT_LOCALE') == 'es'
    assert app.config.get('BABEL_DEFAULT_TIMEZONE') == 'America/Guatemala'


def test_default_locale_is_spanish(client):
    """Test that default page loads in Spanish."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Bienvenido a NexoAI' in response.data
    assert b'Iniciar sesi\xc3\xb3n' in response.data


def test_query_param_language_switch(client):
    """Test switching language via query parameter."""
    # K'iche'
    res_qu = client.get('/?lang=qu')
    assert res_qu.status_code == 200
    assert 'Utz petik pa NexoAI'.encode('utf-8') in res_qu.data
    assert 'Okinik'.encode('utf-8') in res_qu.data

    # Kaqchikel
    res_cak = client.get('/?lang=cak')
    assert res_cak.status_code == 200
    assert 'Ütz ipetik pa NexoAI'.encode('utf-8') in res_cak.data
    assert 'Okem'.encode('utf-8') in res_cak.data

    # Q'eqchi'
    res_qeq = client.get('/?lang=qeq')
    assert res_qeq.status_code == 200
    assert 'Sahil ch\'oolejil sa\' NexoAI'.encode('utf-8') in res_qeq.data
    assert 'Okenk'.encode('utf-8') in res_qeq.data


def test_session_language_persistence(client):
    """Test that selected language persists across subsequent requests in the session."""
    client.get('/set-language/cak')
    
    # Requesting without lang query param should keep Kaqchikel
    response = client.get('/')
    assert response.status_code == 200
    assert 'Ütz ipetik pa NexoAI'.encode('utf-8') in response.data


def test_set_language_endpoint(client):
    """Test /set-language/<lang> route redirects back to referrer or next param."""
    # Test with next parameter
    res_next = client.get('/set-language/qu?next=/expenses')
    assert res_next.status_code == 302
    assert res_next.headers['Location'] == '/expenses'

    # Test with Referer header
    response = client.get('/set-language/qu', headers={'Referer': '/login'})
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'

    # Check that session language is set
    with client.session_transaction() as sess:
        assert sess.get('lang') == 'qu'


def test_set_invalid_language_fallback(client):
    """Test that invalid language code falls back gracefully to default."""
    response = client.get('/set-language/invalid_lang')
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get('lang') == 'es'


def test_user_model_language_preference(app, client):
    """Test that User model stores language and applies when authenticated."""
    with app.app_context():
        user = User(username='testmaya', email='testmaya@example.com', language='qeq')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    # Log in
    login_res = client.post('/login', data={'email': 'testmaya@example.com', 'password': 'password123'}, follow_redirects=True)
    assert login_res.status_code == 200

    # Dashboard should show in user's preferred language (Q'eqchi')
    dash_res = client.get('/dashboard')
    assert dash_res.status_code == 200
    assert 'Xna\'ajil k\'anjel'.encode('utf-8') in dash_res.data or 'Xk\'utb\'esinkil'.encode('utf-8') in dash_res.data

    # Changing language should update user in DB
    client.get('/set-language/qu')
    with app.app_context():
        updated_user = db.session.get(User, user_id)
        assert updated_user.language == 'qu'


def test_navbar_language_dropdown(client):
    """Test that the language dropdown is present on pages."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'id="langDropdown"' in response.data
    assert b'/set-language/es' in response.data
    assert b'/set-language/qu' in response.data
    assert b'/set-language/cak' in response.data
    assert b'/set-language/qeq' in response.data
