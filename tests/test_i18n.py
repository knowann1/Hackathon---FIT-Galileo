"""Regression tests for the multi-language (i18n) support.

These tests reproduce the "Internal Server Error" reported when switching
the dashboard language to anything other than Spanish, and validate that:

  * Switching to any configured language (including ones not present in
    Babel/CLDR locale data, such as Kaqchikel ``cak`` and Q'eqchi' ``qeq``)
    always returns HTTP 200, never a 500.
  * The selected language is reflected across the main pages of the site
    (dashboard, expenses, chatbot), not just a single section.
  * The language preference persists across requests once set.
  * An invalid/unsupported locale value never breaks the app; it safely
    falls back to the current/default language instead.

Run with: python -m unittest discover -s tests
"""

import os
import tempfile
import unittest


class I18nTestCase(unittest.TestCase):
    """Flask-SQLAlchemy/Flask-Login/Flask-Babel are configured as global
    singletons in ``extensions.py`` and rebinding them to a new Flask app on
    every ``create_app()`` call can leak state across app instances within
    the same process. To keep these tests reliable we build the Flask app
    and register the test user once for the whole test case instead of once
    per test method."""

    @classmethod
    def setUpClass(cls):
        cls._db_fd, cls._db_path = tempfile.mkstemp(suffix='.db')
        os.environ['DATABASE_URL'] = 'sqlite:///' + cls._db_path
        os.environ['CREATE_DB'] = '1'
        os.environ['SECRET_KEY'] = 'test-secret-key'

        # Import after env vars are set so Config picks them up.
        from app import create_app

        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

        # Register the test user once; each test logs in with a fresh
        # client/session instead of re-registering.
        setup_client = cls.app.test_client()
        setup_client.post(
            '/register',
            data={
                'username': 'tester',
                'email': 'tester@example.com',
                'password': 'password123',
            },
        )

    @classmethod
    def tearDownClass(cls):
        os.close(cls._db_fd)
        os.remove(cls._db_path)

    def setUp(self):
        # Fresh client (and therefore a fresh session/cookie jar) per test so
        # language selection in one test never leaks into another.
        self.client = self.app.test_client()
        self.client.post(
            '/login',
            data={'email': 'tester@example.com', 'password': 'password123'},
        )

    def test_switching_to_every_supported_language_returns_200(self):
        """Changing to any language configured in config.LANGUAGES must not
        raise an Internal Server Error, including languages that are not
        recognized by Babel/CLDR (cak, qeq)."""
        for lang in self.app.config['LANGUAGES']:
            with self.subTest(lang=lang):
                response = self.client.get('/dashboard?lang=' + lang)
                self.assertEqual(response.status_code, 200)

    def test_main_pages_render_in_selected_language(self):
        """The selected language should affect the whole site, not just one
        page: dashboard, expenses and the AI chatbot should all reflect the
        same translated navigation string once a language is selected."""
        # "Panel" ("Dashboard") is translated for every supported language.
        translations = {
            'es': 'Panel',
            'qu': "Ruwächal",
            'cak': "Samajib'äl",
        }
        for lang, expected in translations.items():
            with self.subTest(lang=lang):
                self.client.get('/dashboard?lang=' + lang)
                for path in ('/dashboard', '/expenses/', '/api/ai/chat'):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    body = response.get_data(as_text=True)
                    self.assertIn(expected, body)

    def test_language_preference_persists_without_query_param(self):
        """Once a language is selected it must persist for subsequent
        requests that do not include the ?lang= query string."""
        self.client.get('/dashboard?lang=cak')
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Samajib'äl", body)

    def test_invalid_locale_falls_back_safely(self):
        """An unsupported/invalid locale code must never cause a 500; the
        app should keep using the current/default language instead."""
        response = self.client.get('/dashboard?lang=not-a-real-locale')
        self.assertEqual(response.status_code, 200)

    def test_missing_translation_key_falls_back_to_source_string(self):
        """If a translation key is missing from a catalog, the app must
        fall back to the original string instead of raising an error."""
        import i18n

        with self.app.test_request_context('/dashboard'):
            result = i18n.gettext('This key does not exist in any catalog')
            self.assertEqual(
                result, 'This key does not exist in any catalog'
            )


if __name__ == '__main__':
    unittest.main()
