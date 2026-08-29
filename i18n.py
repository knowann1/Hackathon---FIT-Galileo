"""Custom i18n helpers.

Flask-Babel resolves translations through ``babel.Locale.parse``, which only
understands valid CLDR locale identifiers. Some of the languages supported by
this app ("cak" for Kaqchikel and "qeq" for Q'eqchi') are not valid CLDR
locale codes, so calling ``Locale.parse('cak')`` raises
``babel.core.UnknownLocaleError`` and turns any page render into a 500 error
as soon as a translatable string is rendered.

To support every language configured in ``config.LANGUAGES`` without
depending on Babel's locale parsing, we install our own ``gettext``/
``ngettext`` callables backed directly on Python's standard ``gettext``
module. These callables read the language straight from the current
request/session (see ``get_current_lang``) instead of going through
``flask_babel.get_locale()``, so an unrecognized locale code never reaches
``babel.Locale.parse``.
"""

import gettext as gettext_module
import os

from flask import current_app, session

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), 'translations')
DOMAIN = 'messages'

_translations_cache = {}


def get_current_lang():
    """Return the language code that should be used for the current request.

    Mirrors the logic used to pick the Babel locale (session override, then
    the authenticated user's stored preference, then the app default) but
    never raises, even for locale codes Babel itself can't parse.
    """
    languages = current_app.config.get('LANGUAGES', {}) if current_app else {}
    default = current_app.config.get('BABEL_DEFAULT_LOCALE', 'es') if current_app else 'es'

    lang = session.get('lang')
    if lang in languages:
        return lang

    try:
        from flask_login import current_user
        if current_user.is_authenticated and getattr(current_user, 'language', None) in languages:
            return current_user.language
    except Exception:
        pass

    return default


def _get_translations(lang):
    """Load (and cache) the stdlib gettext translations for ``lang``."""
    if lang not in _translations_cache:
        try:
            _translations_cache[lang] = gettext_module.translation(
                DOMAIN,
                localedir=TRANSLATIONS_DIR,
                languages=[lang],
                fallback=True,
            )
        except Exception:
            _translations_cache[lang] = gettext_module.NullTranslations()
    return _translations_cache[lang]


def gettext(string):
    translations = _get_translations(get_current_lang())
    return translations.gettext(string)


def ngettext(singular, plural, n):
    translations = _get_translations(get_current_lang())
    return translations.ngettext(singular, plural, n)


def install_gettext_callables(app):
    """Wire up Jinja's ``_``/``gettext``/``ngettext`` to our stdlib-based
    translator, bypassing Flask-Babel's Locale-dependent lookup entirely."""
    app.jinja_env.install_gettext_callables(
        gettext=gettext,
        ngettext=ngettext,
        newstyle=True,
    )
