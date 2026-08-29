import os
from flask import Flask, render_template, session, g, request
from config import Config
from extensions import db, migrate, login_manager, csrf, babel
from routes.auth import auth_bp
from routes.expenses import expenses_bp
from routes.dashboard import dashboard_bp
from routes.ai import ai_bp
from routes.receipts import receipts_bp
from routes.voice import voice_bp
from marketnexo import marketnexo_bp
from flask_login import current_user
from i18n import get_babel_safe_locale, get_current_locale, get_translations


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions.
    # NOTE: Flask-Babel's ``locale_selector`` is only used for its internal
    # (CLDR-dependent) machinery. The actual translated text shown in
    # templates/flash messages comes from ``i18n.get_translations`` (stdlib
    # gettext), which never raises for unsupported/invalid locale codes.
    # See ``get_babel_safe_locale`` for why this split is necessary.
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    babel.init_app(app, locale_selector=get_babel_safe_locale)

    # Language selector before request
    @app.before_request
    def before_request():
        if 'lang' in request.args:
            lang = request.args.get('lang')
            if lang in app.config['LANGUAGES']:
                session['lang'] = lang
                # Update user's language preference if authenticated
                if current_user.is_authenticated and hasattr(current_user, 'language'):
                    current_user.language = lang
                    db.session.commit()
            else:
                app.logger.warning(
                    "Se intentó cambiar a un idioma no soportado ('%s'). "
                    "Se ignora y se conserva el idioma actual.", lang
                )
        g.locale = get_current_locale()

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

    # Provide CSRF token + i18n helpers to templates.
    #
    # ``gettext``/``ngettext``/``_`` are injected here (instead of relying on
    # Flask-Babel's Jinja i18n extension) so that translations always come
    # from ``i18n.get_translations`` -- which never raises for a locale that
    # Babel's CLDR data doesn't recognize, and safely falls back to the
    # default locale (or the original text) when a catalog/key is missing.
    try:
        from flask_wtf.csrf import generate_csrf

        @app.context_processor
        def inject_i18n():
            locale = get_current_locale()
            translations = get_translations(locale)
            return dict(
                csrf_token=generate_csrf,
                LANGUAGES=app.config['LANGUAGES'],
                current_locale=locale,
                gettext=translations.gettext,
                ngettext=translations.ngettext,
                _=translations.gettext,
            )
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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5002)), debug=True)
