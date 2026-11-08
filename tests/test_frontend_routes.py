from __future__ import annotations


def test_fallback_frontend_shell_and_assets_are_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Smart Meter Explorer V2" in page.text
    assert 'href="/styles.css"' in page.text
    assert 'src="/app.js"' in page.text

    stylesheet = client.get("/styles.css")
    script = client.get("/app.js")
    assert stylesheet.status_code == 200
    assert "prefers-reduced-motion" in stylesheet.text
    assert script.status_code == 200
    assert "Pulse Ring" in script.text or "pulse-ring" in script.text

    assert page.headers.get("X-Content-Type-Options") == "nosniff"
    assert page.headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'self'" in page.headers.get("Content-Security-Policy", "")
    assert "https://api.open-meteo.com" in page.headers.get("Content-Security-Policy", "")
    assert "geolocation=(self)" in page.headers.get("Permissions-Policy", "")


def test_unknown_frontend_asset_returns_not_found(client):
    response = client.get("/this-file-does-not-exist.js")
    assert response.status_code == 404
