from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
babel = Babel()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión.'
