"""Internationalization helpers for NexoAI.

Why this module exists
-----------------------
Flask-Babel (and the underlying ``babel`` library) resolves translation
catalogs through ``babel.Locale.parse()``. That call validates the locale
code against Unicode CLDR data. Several of the languages offered in the
dashboard's language selector (Mayan languages such as Kaqchikel ``cak``
and Q'eqchi' ``qeq``) do **not** have CLDR entries, so ``Locale.parse()``
raises ``babel.core.UnknownLocaleError`` the moment a template calls
``_()`` -- this was the exact root cause of the "Internal Server Error"
reported when a user picked anything other than Spanish.

To fix this robustly (and avoid ever depending on CLDR having data for a
given locale) we load translation catalogs directly with the Python
standard library ``gettext`` module, which only cares about the presence
of a ``translations/<locale>/LC_MESSAGES/messages.mo`` file -- not about
whether the locale code is a "real" CLDR identifier.
"""

import gettext as gettext_module
import logging

from flask import current_app, session

logger = logging.getLogger(__name__)

# Translation objects are stateless and cheap to reuse across requests.
_translations_cache = {}


def get_allowed_languages():
    """Return the dict of locale-code -> display-name configured for the app."""
    return current_app.config.get('LANGUAGES', {'es': 'Español'})


def get_default_locale():
    return current_app.config.get('BABEL_DEFAULT_LOCALE', 'es')


def is_supported_locale(locale):
    """Validate an incoming locale code against the configured allow-list."""
    return bool(locale) and locale in get_allowed_languages()


def get_current_locale():
    """Resolve the locale to use for the current request.

    Order of precedence:
    1. Locale stored in the session (set by the language selector).
    2. Authenticated user's saved language preference (if the model has one).
    3. The application's configured default locale.

    Any value that isn't in the configured allow-list is ignored so that a
    tampered cookie/session or a removed language can never crash the app.
    """
    from flask_login import current_user  # local import: avoids app-context issues

    default_locale = get_default_locale()

    lang = session.get('lang')
    if is_supported_locale(lang):
        return lang

    try:
        if current_user and getattr(current_user, 'is_authenticated', False):
            user_lang = getattr(current_user, 'language', None)
            if is_supported_locale(user_lang):
                return user_lang
    except Exception:  # pragma: no cover - defensive, e.g. no request context
        pass

    return default_locale if is_supported_locale(default_locale) else 'es'


def get_babel_safe_locale():
    """Return a locale string that is guaranteed to be parseable by Babel's
    ``Locale.parse`` (used as Flask-Babel's ``locale_selector``).

    This does not affect which translation catalog is shown to the user
    (see :func:`translate`/:func:`get_translations`, which use the raw
    locale from :func:`get_current_locale`); it only prevents Flask-Babel's
    internal machinery (e.g. date/number formatting) from raising
    ``UnknownLocaleError`` for locales that have no CLDR data.
    """
    from babel import Locale, UnknownLocaleError

    locale = get_current_locale()
    try:
        Locale.parse(locale)
        return locale
    except (UnknownLocaleError, ValueError):
        return get_default_locale()


def get_translations(locale=None):
    """Load (and cache) a gettext catalog for ``locale`` with a safe fallback.

    Falls back to the default locale's catalog if the requested one is
    missing, and to ``NullTranslations`` (i.e. the original msgid text) if
    even the default catalog can't be found -- so a missing/incomplete
    translation catalog can never result in a 500 error.
    """
    locale = locale or get_current_locale()

    if locale in _translations_cache:
        return _translations_cache[locale]

    translations_dir = current_app.config.get(
        'BABEL_TRANSLATION_DIRECTORIES', 'translations'
    )
    default_locale = get_default_locale()

    try:
        translations = gettext_module.translation(
            'messages', translations_dir, languages=[locale]
        )
    except (FileNotFoundError, OSError):
        logger.warning(
            "No se encontró un catálogo de traducción compilado para el "
            "idioma '%s'. Aplicando respaldo al idioma por defecto '%s'.",
            locale, default_locale,
        )
        try:
            translations = gettext_module.translation(
                'messages', translations_dir, languages=[default_locale]
            )
        except (FileNotFoundError, OSError):
            logger.warning(
                "No se encontró el catálogo de traducción por defecto '%s'. "
                "Se mostrarán los textos originales sin traducir.",
                default_locale,
            )
            translations = gettext_module.NullTranslations()

    _translations_cache[locale] = translations
    return translations


def translate(msgid, **kwargs):
    """Translate ``msgid`` into the current request's locale.

    Usable both from Jinja templates (as ``_()``/``gettext()``) and from
    plain Python code (e.g. ``flash()`` messages).
    """
    text = get_translations().gettext(msgid)
    if kwargs:
        try:
            return text % kwargs
        except (KeyError, ValueError, TypeError):  # pragma: no cover - defensive
            return text
    return text


def ntranslate(singular, plural, n, **kwargs):
    """Plural-aware translation helper (mirrors ``ngettext``)."""
    text = get_translations().ngettext(singular, plural, n)
    kwargs.setdefault('num', n)
    try:
        return text % kwargs
    except (KeyError, ValueError, TypeError):  # pragma: no cover - defensive
        return text
