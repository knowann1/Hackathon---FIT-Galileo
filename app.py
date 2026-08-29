import os
from flask import Flask, render_template, request, session, g, redirect, url_for
from flask_login import current_user
from flask_babel import refresh
from babel import Locale
from config import Config
from extensions import db, migrate, login_manager, csrf, babel
from routes.auth import auth_bp
from routes.expenses import expenses_bp
from routes.dashboard import dashboard_bp
from routes.ai import ai_bp
from routes.receipts import receipts_bp
from routes.voice import voice_bp
from marketnexo import marketnexo_bp


class CustomLocale(Locale):
    """Custom Locale wrapper for indigenous/non-standard ISO locales like cak and qeq."""
    def __init__(self, identifier):
        self.language = identifier
        self.territory = None
        self.script = None
        self.variant = None
        self._identifier = identifier

    def __str__(self):
        return self._identifier

    def __repr__(self):
        return f"CustomLocale('{self._identifier}')"


def safe_locale(code):
    """Return a standard Locale object or a CustomLocale instance if unknown to Babel CLDR."""
    if isinstance(code, Locale):
        return code
    try:
        return Locale.parse(code)
    except Exception:
        return CustomLocale(code)


def create_app(config_object=Config):
    app = Flask(__name__)
    if isinstance(config_object, dict):
        app.config.from_object(Config)
        app.config.update(config_object)
    elif config_object is not None:
        app.config.from_object(config_object)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Locale selector for Flask-Babel
    def get_locale():
        # 1. URL query parameter
        lang = request.args.get('lang')
        if lang and lang in app.config.get('LANGUAGES', {}):
            return safe_locale(lang)

        # 2. Session
        if 'lang' in session and session['lang'] in app.config.get('LANGUAGES', {}):
            return safe_locale(session['lang'])

        # 3. Authenticated user saved preference
        if current_user and current_user.is_authenticated and hasattr(current_user, 'language') and current_user.language in app.config.get('LANGUAGES', {}):
            return safe_locale(current_user.language)

        # 4. Default locale
        return safe_locale(app.config.get('BABEL_DEFAULT_LOCALE', 'es'))

    babel.init_app(app, locale_selector=get_locale)

    @app.before_request
    def before_request():
        refresh()
        lang = request.args.get('lang')
        if lang and lang in app.config.get('LANGUAGES', {}):
            session['lang'] = lang
            if current_user and current_user.is_authenticated and hasattr(current_user, 'language') and current_user.language != lang:
                current_user.language = lang
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        g.locale = str(get_locale())

    @app.context_processor
    def inject_locale():
        locale = get_locale()
        return dict(
            get_locale=get_locale,
            current_locale=str(locale),
            LANGUAGES=app.config.get('LANGUAGES', {})
        )

    # Create database tables if they don't exist yet (helps for local/dev runs)
    # This uses SQLAlchemy's create_all and runs inside the app context.
    # Controlled by CREATE_DB env var; default is '1' to enable table creation.
    try:
        if os.getenv('CREATE_DB', '1') == '1':
            with app.app_context():
                db.create_all()
    except Exception:
        # If something goes wrong here, avoid crashing app creation; errors will
        # still surface when accessing DB operations.
        pass

    # User loader for Flask-Login
    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Provide CSRF token helper to templates
    try:
        from flask_wtf.csrf import generate_csrf

        @app.context_processor
        def inject_csrf_token():
            return dict(csrf_token=generate_csrf)
    except Exception:
        pass

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(expenses_bp, url_prefix="/expenses")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(receipts_bp, url_prefix="/receipts")
    app.register_blueprint(voice_bp, url_prefix="/voice")
    app.register_blueprint(marketnexo_bp, url_prefix="/marketnexo")

    @app.route("/")
    def index():
        # Renderizar la plantilla index.html como página principal (sin cambiar la URL)
        return render_template('index.html')

    @app.route("/set-language/<lang>")
    def set_language(lang):
        if lang in app.config.get('LANGUAGES', {}):
            session['lang'] = lang
            if current_user and current_user.is_authenticated and hasattr(current_user, 'language') and current_user.language != lang:
                current_user.language = lang
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        else:
            session['lang'] = app.config.get('BABEL_DEFAULT_LOCALE', 'es')
        refresh()
        next_url = request.referrer or url_for('index')
        return redirect(next_url)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5002)), debug=True)
