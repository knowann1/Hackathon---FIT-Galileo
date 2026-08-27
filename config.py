import os
from datetime import timedelta

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'data.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

    # File upload limits
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024  # 6 MB
    UPLOAD_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf', '.wav', '.mp3', '.m4a', '.webm', '.ogg']
    UPLOAD_PATH = os.path.join(basedir, 'static', 'uploads')
