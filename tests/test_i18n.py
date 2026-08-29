"""Tests for the i18n (internationalization) behavior of NexoAI.

These tests cover the requirements from the bug report:
  a) switching language responds 200 (never 500),
  b) main pages actually render in the selected language,
  c) redirects/navigation preserve the selected language,
  d) missing/invalid locale or translation key falls back safely.
"""

import re

import pytest

from config import Config
from i18n import get_translations


ALL_LANGUAGES = list(Config.LANGUAGES.keys())  # es, qu, cak, qeq


def _h2_text(html_bytes):
    match = re.search(rb'<h2>(.*?)</h2>', html_bytes)
    return match.group(1).decode('utf-8') if match else None


def _html_lang_attr(html_bytes):
    match = re.search(rb'<html lang="(.*?)">', html_bytes)
    return match.group(1).decode('utf-8') if match else None


@pytest.mark.parametrize('lang', ALL_LANGUAGES)
def test_switching_language_never_returns_500(client, registered_user, lang):
    """(a) Selecting any configured language must never crash with a 500."""
    response = client.get(f'/dashboard?lang={lang}')
    assert response.status_code == 200


def test_invalid_locale_falls_back_safely(client, registered_user):
    """(d) An unsupported/unknown locale must not crash the app."""
    response = client.get('/dashboard?lang=doesnotexist')
    assert response.status_code == 200
    # Falls back to the default locale (Spanish) instead of raising.
    assert _h2_text(response.data) == 'Resumen'


@pytest.mark.parametrize('lang', ALL_LANGUAGES)
def test_main_pages_render_in_selected_language(client, registered_user, lang):
    """(b) The dashboard (a key page) must render translated content."""
    response = client.get(f'/dashboard?lang={lang}')
    assert response.status_code == 200
    expected = get_translations(lang).gettext('Resumen')
    assert _h2_text(response.data) == expected
    assert _html_lang_attr(response.data) == lang


def test_navbar_translates_across_languages(client, registered_user):
    """Different languages must actually produce different rendered text."""
    resp_es = client.get('/dashboard?lang=es')
    resp_cak = client.get('/dashboard?lang=cak')
    assert _h2_text(resp_es.data) != _h2_text(resp_cak.data)


def test_language_choice_persists_across_navigation(client, registered_user):
    """(c) After selecting a language, subsequent requests (without the
    ?lang= query string) must keep using that language."""
    r = client.get('/dashboard?lang=cak')
    assert r.status_code == 200
    assert _html_lang_attr(r.data) == 'cak'

    # Navigate to a different page with no lang param: locale must persist.
    r = client.get('/expenses/')
    assert r.status_code == 200
    assert _html_lang_attr(r.data) == 'cak'


def test_language_choice_persists_after_logout_redirect(client, registered_user):
    """(c) Redirects (e.g. logout -> login) must preserve the language."""
    r = client.get('/dashboard?lang=qeq')
    assert r.status_code == 200

    r = client.get('/logout', follow_redirects=True)
    assert r.status_code == 200
    assert _html_lang_attr(r.data) == 'qeq'


def test_login_page_translates_title(client, registered_user):
    r = client.get('/logout')
    r = client.get('/login?lang=qu')
    assert r.status_code == 200
    match = re.search(rb'<h3>(.*?)</h3>', r.data)
    assert match is not None
    rendered_title = match.group(1).decode('utf-8').replace('&#39;', "'")
    expected = get_translations('qu').gettext('Iniciar sesión')
    assert rendered_title == expected


def test_unsupported_locale_query_param_is_ignored(client, registered_user):
    """Setting an unsupported ?lang= must not overwrite a valid session
    locale, and must not raise an error."""
    client.get('/dashboard?lang=qu')
    r = client.get('/dashboard?lang=not-a-real-locale')
    assert r.status_code == 200
    assert _html_lang_attr(r.data) == 'qu'


def test_get_translations_falls_back_when_catalog_missing(app):
    """(d) If a locale has no compiled catalog at all, fall back to the
    default locale instead of raising, and never return None."""
    with app.test_request_context('/'):
        translations = get_translations('xx-does-not-exist')
        assert translations is not None
        # Falls back to default locale's catalog, so a known key still
        # resolves to a translated (or at worst original) string.
        assert translations.gettext('Panel') != ''
