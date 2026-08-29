"""Helpers to support languages that aren't valid CLDR locale codes.

Kaqchikel ('cak') and Q'eqchi' ('qeq') are not valid CLDR locale
identifiers, so ``babel.Locale.parse()`` raises ``UnknownLocaleError`` for
them. Flask-Babel relies on ``Locale.parse()`` internally for every
translation lookup, so those two languages need to bypass Flask-Babel's
Locale-dependent gettext and use Python's stdlib ``gettext`` module
directly against the compiled catalogs in ``translations/``.
"""
import os
import gettext as gettext_module

# Languages configured in config.LANGUAGES that Babel's Locale.parse()
# cannot understand.
NON_CLDR_LANGUAGES = {'cak', 'qeq'}

_TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), 'translations')
_translations_cache = {}


def get_stdlib_translations(lang):
    """Return a stdlib ``gettext`` translations object for ``lang``.

    Falls back to ``NullTranslations`` (i.e. untranslated source text) if
    no compiled catalog is available for the language.
    """
    if lang not in _translations_cache:
        try:
            _translations_cache[lang] = gettext_module.translation(
                'messages', _TRANSLATIONS_DIR, languages=[lang]
            )
        except FileNotFoundError:
            _translations_cache[lang] = gettext_module.NullTranslations()
    return _translations_cache[lang]
