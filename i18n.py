import gettext as py_gettext
import json
import os
from flask import g, session
from flask_login import current_user

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), 'translations')

LANGUAGE_ALIASES = {
    'es': 'es',
    'spanish': 'es',
    'español': 'es',
    'qu': 'qu',
    'quc': 'qu',
    'kiche': 'qu',
    "k'iche'": 'qu',
    'cak': 'cak',
    'kaqchikel': 'cak',
    'qeq': 'qeq',
    'qeqchi': 'qeq',
    "q'eqchi'": 'qeq'
}

_translations_cache = {}


def normalize_language_code(code):
    """Normalize language aliases to canonical codes (es, qu, cak, qeq)."""
    if not code:
        return 'es'
    code = str(code).lower().strip()
    return LANGUAGE_ALIASES.get(code, code if code in ('es', 'qu', 'cak', 'qeq') else 'es')


def get_current_locale():
    """Determine the current active locale."""
    # 1. Query parameter override (?lang=...)
    try:
        from flask import request
        if request and request.args and 'lang' in request.args:
            raw_lang = request.args.get('lang')
            if raw_lang:
                return normalize_language_code(raw_lang)
    except Exception:
        pass

    # 2. Session preference
    try:
        from flask import session
        if session and 'lang' in session and session.get('lang'):
            return normalize_language_code(session.get('lang'))
    except Exception:
        pass

    # 3. Authenticated user preference in database
    try:
        if current_user and current_user.is_authenticated and hasattr(current_user, 'language') and current_user.language:
            return normalize_language_code(current_user.language)
    except Exception:
        pass

    return 'es'


def get_translation_catalog(lang=None):
    """Get the GNUTranslations object for a given language."""
    lang = normalize_language_code(lang or get_current_locale())
    if lang not in _translations_cache:
        try:
            _translations_cache[lang] = py_gettext.translation(
                'messages',
                localedir=TRANSLATIONS_DIR,
                languages=[lang],
                fallback=True
            )
        except Exception:
            _translations_cache[lang] = py_gettext.NullTranslations()
    return _translations_cache[lang]


def custom_gettext(message, lang=None):
    """Translate a message string using stdlib gettext."""
    if not message:
        return message
    catalog = get_translation_catalog(lang)
    return catalog.gettext(message)


def custom_ngettext(singular, plural, n, lang=None):
    """Translate singular/plural strings."""
    catalog = get_translation_catalog(lang)
    return catalog.ngettext(singular, plural, n)


# Aliases for convenience
resolve_locale_code = normalize_language_code
translate = custom_gettext
gettext = custom_gettext
ngettext = custom_ngettext


_all_translations_cache = None


def get_all_translations():
    """Return all translations as a dictionary of key-value pairs per language (cached in memory)."""
    global _all_translations_cache
    if _all_translations_cache is not None:
        return _all_translations_cache

    all_trans = {}
    languages = ['es', 'qu', 'cak', 'qeq']
    
    # Read the msgids from the .po files
    po_files = {
        'es': os.path.join(TRANSLATIONS_DIR, 'es', 'LC_MESSAGES', 'messages.po'),
        'qu': os.path.join(TRANSLATIONS_DIR, 'qu', 'LC_MESSAGES', 'messages.po'),
        'cak': os.path.join(TRANSLATIONS_DIR, 'cak', 'LC_MESSAGES', 'messages.po'),
        'qeq': os.path.join(TRANSLATIONS_DIR, 'qeq', 'LC_MESSAGES', 'messages.po')
    }

    for lang in languages:
        catalog = get_translation_catalog(lang)
        all_trans[lang] = {}
        po_path = po_files.get(lang)
        if po_path and os.path.exists(po_path):
            with open(po_path, 'r', encoding='utf-8') as f:
                content = f.read()
            import re
            entries = re.findall(r'msgid\s+"(.+?)"\s+msgstr\s+"(.*?)"', content, re.DOTALL)
            for msgid, msgstr in entries:
                if msgid:
                    # Unescape standard gettext escapes
                    msgid_unescaped = msgid.replace('\\"', '"').replace('\\n', '\n')
                    all_trans[lang][msgid_unescaped] = catalog.gettext(msgid_unescaped)
        # Also alias for frontend compatibility
        if lang == 'qu':
            all_trans['kiche'] = all_trans[lang]
        elif lang == 'cak':
            all_trans['kaqchikel'] = all_trans[lang]
        elif lang == 'qeq':
            all_trans['qeqchi'] = all_trans[lang]

    _all_translations_cache = all_trans
    return _all_translations_cache
