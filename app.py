import os
from flask import Flask, render_template, session, g, request
from flask_babel import Babel, gettext
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


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    babel.init_app(app)

    # Babel locale selector
    @babel.localeselector
    def get_locale():
        # First check if user has set language preference in session
        if 'lang' in session:
            return session['lang']
        # Check if user is authenticated and has language preference
        if current_user.is_authenticated and hasattr(current_user, 'language') and current_user.language:
            return current_user.language
        # Fall back to default
        return app.config['BABEL_DEFAULT_LOCALE']

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
        g.locale = get_locale()

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
            return dict(
                csrf_token=generate_csrf,
                LANGUAGES=app.config['LANGUAGES'],
                current_locale=get_locale()
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
