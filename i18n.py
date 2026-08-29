"""Safe internationalization helpers.

This module centralizes locale resolution and message translation so the
application never raises a 500 error because of an unsupported or invalid
locale code.

Why this exists
----------------
Flask-Babel/Babel resolve locales using ``babel.Locale.parse``, which relies
on CLDR locale data. Some of the languages offered by the dashboard language
selector (for example Kaqchikel ``cak`` and Q'eqchi' ``qeq``) are not part of
CLDR, so ``Locale.parse('cak')`` raises ``UnknownLocaleError`` and, left
unhandled, that bubbles up as an ``Internal Server Error`` on every page that
renders a translated string.

To keep those languages fully usable we:
  * Resolve/validate the active locale ourselves (``get_locale``), always
    falling back to the configured default language when the requested one
    is missing, unsupported or otherwise invalid.
  * Load translation catalogs directly with the standard library ``gettext``
    module (``_get_translations``), which only needs a directory and a
    language code and does not require the language to exist in CLDR.
  * Expose ``gettext``/``ngettext`` wrappers that are installed as the Jinja
    ``_()``/``ngettext()`` callables, replacing Flask-Babel's versions which
    would otherwise crash for these locales.
"""

import gettext as gettext_lib
import os

from flask import current_app, session
from flask_login import current_user

TRANSLATIONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'translations'
)

# Cache of loaded gettext.Translations objects keyed by language code.
_translations_cache = {}


def get_locale():
    """Return a validated language code for the current request.

    Always returns a key present in ``app.config['LANGUAGES']``. Falls back
    to the authenticated user's stored preference, and finally to the app's
    default locale, so an invalid/missing value never propagates further.
    """
    app = current_app
    languages = app.config.get('LANGUAGES', {}) or {}
    default_locale = app.config.get('BABEL_DEFAULT_LOCALE', 'es')

    lang = session.get('lang')
    if lang not in languages:
        lang = None
        try:
            if current_user.is_authenticated:
                user_lang = getattr(current_user, 'language', None)
                if user_lang in languages:
                    lang = user_lang
        except Exception:
            # current_user may be unavailable outside of a request context.
            lang = None

    if lang not in languages:
        lang = default_locale

    # Final safety net: if the default itself was misconfigured, fall back
    # to Spanish which always ships with this application.
    if lang not in languages:
        lang = 'es'

    return lang


def babel_locale_selector():
    """Locale selector used by Flask-Babel for date/number formatting.

    Flask-Babel requires a locale that Babel's CLDR data recognizes. Some of
    our supported languages (e.g. ``cak``, ``qeq``) are not in CLDR, so for
    those we fall back to the default locale for formatting purposes only;
    message translation is handled separately via ``gettext``/``ngettext``
    below and is unaffected by this fallback.
    """
    from babel import Locale
    from babel.core import UnknownLocaleError

    app = current_app
    lang = get_locale()
    try:
        Locale.parse(lang)
        return lang
    except (UnknownLocaleError, ValueError, TypeError):
        return app.config.get('BABEL_DEFAULT_LOCALE', 'es')


def _get_translations(lang):
    """Load (and cache) a gettext translation catalog for ``lang``."""
    app = current_app
    default_locale = app.config.get('BABEL_DEFAULT_LOCALE', 'es')

    cached = _translations_cache.get(lang)
    if cached is not None:
        return cached

    languages = [lang]
    if lang != default_locale:
        languages.append(default_locale)

    try:
        translations = gettext_lib.translation(
            'messages',
            TRANSLATIONS_DIR,
            languages=languages,
            fallback=True,
        )
    except Exception:
        # Never let a missing/corrupt catalog break the page. Fall back to
        # returning the original source strings untranslated.
        translations = gettext_lib.NullTranslations()

    _translations_cache[lang] = translations
    return translations


def gettext(string, **variables):
    """Safe replacement for Flask-Babel's ``gettext``.

    Never raises: if the current locale or catalog is invalid/missing, the
    original string is returned untranslated.
    """
    try:
        translations = _get_translations(get_locale())
        message = translations.gettext(string)
    except Exception:
        message = string
    return message % variables if variables else message


def ngettext(singular, plural, num, **variables):
    """Safe replacement for Flask-Babel's ``ngettext``."""
    variables.setdefault('num', num)
    try:
        translations = _get_translations(get_locale())
        message = translations.ngettext(singular, plural, num)
    except Exception:
        message = singular if num == 1 else plural
    return message % variables
