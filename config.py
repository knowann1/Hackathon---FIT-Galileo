import os
from datetime import timedelta

class Config:
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///financial_ai.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'true').lower() in ('true', '1')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Security
    SECRET_KEY = os.getenv(
        'SECRET_KEY',
        'your-secret-key-change-me'
    )
    WTF_CSRF_ENABLED = True

    # Upload
    UPLOAD_PATH = os.path.join(
        os.path.dirname(__file__),
        'uploads'
    )
    UPLOAD_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.pdf', '.mp3', '.wav', '.m4a', '.ogg', '.webm']
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # Multilingual Support
    LANGUAGES = {
        'es': 'Español',
        'qu': "K'iche'",
        'cak': 'Kaqchikel',
        'qeq': "Q'eqchi'"
    }
    BABEL_DEFAULT_LOCALE = 'es'
    BABEL_DEFAULT_TIMEZONE = 'America/Guatemala'
    BABEL_TRANSLATION_DIRECTORIES = 'translations'

LANGUAGES = Config.LANGUAGES
