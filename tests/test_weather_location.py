from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_weather_location_is_explicit_per_launch_and_skippable():
    source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "weatherPromptedThisLaunch" in source
    assert "weatherModal();" in source
    assert "Use my location" in source
    assert "Not now" in source
    assert "navigator.geolocation.getCurrentPosition" in source
    assert "maximumAge:0" in source.replace(" ", "")
    assert "Coordinates were not stored by this app" in source


def test_weather_fetch_uses_open_meteo_without_server_side_coordinate_storage():
    source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "https://api.open-meteo.com/v1/forecast" in source
    assert "credentials:'omit'" in source
    assert "weather-context-content" in source
    assert "not proof of causation" in source
    backend = (ROOT / "sme" / "main.py").read_text(encoding="utf-8")
    assert "geolocation=(self)" in backend
    assert "https://api.open-meteo.com" in backend
