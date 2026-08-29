import os
import gettext as stdlib_gettext
from flask import session, request, g
from flask_login import current_user

_translations = {}

VALID_LANGUAGES = ('es', 'qu', 'cak', 'qeq')


def get_locale():
    """Determine the active locale for message translation."""
    # 1. URL parameter if present and valid
    if request:
        try:
            if 'lang' in request.args:
                lang = request.args.get('lang')
                if lang in VALID_LANGUAGES:
                    return lang
        except RuntimeError:
            pass

    # 2. Session preference
    try:
        if session and 'lang' in session and session['lang'] in VALID_LANGUAGES:
            return session['lang']
    except RuntimeError:
        pass

    # 3. Authenticated user preference
    try:
        if (
            current_user
            and current_user.is_authenticated
            and hasattr(current_user, 'language')
            and current_user.language in VALID_LANGUAGES
        ):
            return current_user.language
    except (RuntimeError, AttributeError):
        pass

    # 4. Accept-Language header from browser
    try:
        if request and request.accept_languages:
            best = request.accept_languages.best_match(VALID_LANGUAGES)
            if best:
                return best
    except (RuntimeError, Exception):
        pass

    # 5. Default fallback
    return 'es'


def babel_locale_selector():
    """Locale selector for Flask-Babel that returns only CLDR-valid locale codes to avoid UnknownLocaleError."""
    loc = get_locale()
    if loc in ('cak', 'qeq'):
        return 'es'
    return loc


def get_translations_for(locale):
    """Retrieve stdlib GNUTranslations catalog for a given locale."""
    if locale not in _translations:
        localedir = os.path.join(os.path.dirname(__file__), 'translations')
        _translations[locale] = stdlib_gettext.translation(
            'messages',
            localedir=localedir,
            languages=[locale],
            fallback=True
        )
    return _translations[locale]


def gettext(message):
    """Translate message for the current request locale."""
    try:
        loc = getattr(g, 'locale', None) or get_locale()
    except RuntimeError:
        loc = 'es'
    t = get_translations_for(loc)
    return t.gettext(message)


def _(message):
    return gettext(message)
