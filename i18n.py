"""Custom i18n helpers.

Flask-Babel resolves message translations through `babel.Locale.parse`,
which only understands CLDR locale identifiers. Some of the languages
supported by this application - Kaqchikel (`cak`) and Q'eqchi' (`qeq`) -
are not valid CLDR locale codes, so `Locale.parse` raises
`UnknownLocaleError` and crashes the whole request whenever one of them
is selected.

To support these languages we bypass Flask-Babel for message
translation and use Python's standard `gettext` module directly,
loading the `.mo` catalogs found in `translations/<lang>/LC_MESSAGES`.
Flask-Babel itself is still used for date/number formatting, using the
default locale as a safe fallback for these codes (see
`babel_locale_selector` in app.py).
"""
import gettext as gettext_module
import threading

from flask import current_app, session
from flask_login import current_user

DOMAIN = 'messages'

_translations_cache = {}
_translations_lock = threading.Lock()


def get_current_language():
    """Return the raw language code that should be used for this request."""
    app = current_app._get_current_object()
    languages = app.config.get('LANGUAGES', {})

    lang = session.get('lang')
    if lang in languages:
        return lang

    if current_user.is_authenticated and getattr(current_user, 'language', None):
        if current_user.language in languages:
            return current_user.language

    return app.config.get('BABEL_DEFAULT_LOCALE', 'es')


def _get_translations(lang):
    translations = _translations_cache.get(lang)
    if translations is None:
        with _translations_lock:
            translations = _translations_cache.get(lang)
            if translations is None:
                # BABEL_TRANSLATION_DIRECTORIES may contain several
                # semicolon-separated directories; stdlib gettext only
                # accepts a single localedir, so use the first one.
                config_dirs = current_app.config.get(
                    'BABEL_TRANSLATION_DIRECTORIES', 'translations'
                )
                localedir = config_dirs.split(';')[0].strip()
                try:
                    translations = gettext_module.translation(
                        DOMAIN, localedir, languages=[lang], fallback=True
                    )
                except Exception:
                    translations = gettext_module.NullTranslations()
                _translations_cache[lang] = translations
    return translations


def gettext(string):
    return _get_translations(get_current_language()).gettext(string)


def ngettext(singular, plural, num):
    return _get_translations(get_current_language()).ngettext(singular, plural, num)


def install_gettext_callables(app):
    """Install stdlib-gettext-based callables into the Jinja environment.

    This overrides Flask-Babel's Locale-based gettext/ngettext (installed by
    `babel.init_app`), which crashes for non-CLDR language codes such as
    'cak' and 'qeq'.
    """
    app.jinja_env.install_gettext_callables(
        gettext=gettext,
        ngettext=ngettext,
        newstyle=True,
    )
