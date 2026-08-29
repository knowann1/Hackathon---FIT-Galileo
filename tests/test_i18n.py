import pytest
import i18n
from config import LANGUAGES

def test_canonical_locale_resolution():
    assert i18n.resolve_locale_code("es") == "es"
    assert i18n.resolve_locale_code("qu") == "qu"
    assert i18n.resolve_locale_code("kiche") == "qu"
    assert i18n.resolve_locale_code("quc") == "qu"
    assert i18n.resolve_locale_code("cak") == "cak"
    assert i18n.resolve_locale_code("kaqchikel") == "cak"
    assert i18n.resolve_locale_code("qeq") == "qeq"
    assert i18n.resolve_locale_code("qeqchi") == "qeq"
    assert i18n.resolve_locale_code("unknown_lang") == "es"
    assert i18n.resolve_locale_code(None) == "es"

def test_language_mappings_in_config():
    assert "es" in LANGUAGES
    assert "qu" in LANGUAGES
    assert "cak" in LANGUAGES
    assert "qeq" in LANGUAGES
    assert LANGUAGES["qu"] == "K'iche'"
    assert LANGUAGES["cak"] == "Kaqchikel"
    assert LANGUAGES["qeq"] == "Q'eqchi'"

def test_translations_lookup_all_languages():
    # Test Spanish (default)
    assert i18n.translate("Resumen", lang="es") == "Resumen"
    assert i18n.translate("Panel", lang="es") == "Panel"

    # Test K'iche'
    assert i18n.translate("Resumen", lang="qu") == "Xel ri samaj"
    assert i18n.translate("Gastos del mes", lang="qu") == "Kach'apem ri ik'"
    assert i18n.translate("Ingresos del mes", lang="qu") == "Siwan ri ik'"
    assert i18n.translate("Analizar mis finanzas", lang="qu") == "Tik'elixin ri nu kach'apem"

    # Test Kaqchikel
    assert i18n.translate("Resumen", lang="cak") == "Xel ri samaj"
    assert i18n.translate("Gastos del mes", lang="cak") == "Kichoq'om ri ik'"
    assert i18n.translate("Ingresos del mes", lang="cak") == "Kiriquin ri ik'"
    assert i18n.translate("Analizar mis finanzas", lang="cak") == "Tik'elixin ri nu kichoq'om"

    # Test Q'eqchi'
    assert i18n.translate("Resumen", lang="qeq") == "Li xel sa li xbasreba"
    assert i18n.translate("Gastos del mes", lang="qeq") == "Li xqui sa li po"
    assert i18n.translate("Ingresos del mes", lang="qeq") == "Li xriquin sa li po"
    assert i18n.translate("Analizar mis finanzas", lang="qeq") == "Taxila li sa xbasreba"

def test_api_translations_endpoint(client):
    for lang in ["es", "qu", "cak", "qeq"]:
        response = client.get(f"/api/translations?lang={lang}")
        assert response.status_code == 200
        data = response.get_json()
        assert "translations" in data
        assert "Resumen" in data["translations"]

def test_set_language_route(client):
    response = client.get("/set-language/qu", follow_redirects=False)
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("lang") == "qu"

    response = client.get("/set-language/cak", follow_redirects=False)
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("lang") == "cak"

    response = client.get("/set-language/qeq", follow_redirects=False)
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("lang") == "qeq"

def test_dashboard_rendering_kiche(auth_client):
    response = auth_client.get("/dashboard?lang=qu")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Xel ri samaj" in html
    assert "Kach&#39;apem ri ik&#39;" in html or "Kach'apem ri ik'" in html
    assert "Tik&#39;elixin ri nu kach&#39;apem" in html or "Tik'elixin ri nu kach'apem" in html

def test_dashboard_rendering_kaqchikel(auth_client):
    response = auth_client.get("/dashboard?lang=cak")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Xel ri samaj" in html
    assert "Kichoq&#39;om ri ik&#39;" in html or "Kichoq'om ri ik'" in html
    assert "Tik&#39;elixin ri nu kichoq&#39;om" in html or "Tik'elixin ri nu kichoq'om" in html

def test_dashboard_rendering_qeqchi(auth_client):
    response = auth_client.get("/dashboard?lang=qeq")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Li xel sa li xbasreba" in html
    assert "Li xqui sa li po" in html
    assert "Taxila li sa xbasreba" in html

def test_language_persistence_across_requests(auth_client):
    # Switch to Kaqchikel
    res1 = auth_client.get("/set-language/cak")
    assert res1.status_code == 302
    
    # Check that expenses page is rendered in Kaqchikel
    response = auth_client.get("/expenses/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Kichoq&#39;om" in html or "Kichoq'om" in html or "Tiquin" in html

def test_set_language_redirect_safety(client):
    # Unsafe external redirect should fallback to '/'
    response = client.get("/set-language/es?next=https://evil.com", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers.get("Location") == "/"

    response = client.get("/set-language/es?next=//evil.com", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers.get("Location") == "/"

    # Safe internal redirect should be respected
    response = client.get("/set-language/es?next=/expenses/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers.get("Location") == "/expenses/"

    # Referrer fallback on same host
    response = client.get(
        "/set-language/es",
        headers={"Referer": "http://localhost/dashboard"},
        follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers.get("Location") == "/dashboard"

    # External referrer should fallback to '/'
    response = client.get(
        "/set-language/es",
        headers={"Referer": "http://external-evil.com/dashboard"},
        follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers.get("Location") == "/"
