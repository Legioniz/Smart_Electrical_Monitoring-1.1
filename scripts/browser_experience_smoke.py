#!/usr/bin/env python3
"""Optional real-browser smoke test for the local fallback UI.

Install with: python -m pip install -r requirements-browser.txt
Then install a browser with: python -m playwright install chromium
This starts an isolated in-memory SQLite test app; it never touches the user's DB.
"""
from __future__ import annotations

import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(url: str, timeout: float = 12.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    return False


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
        import uvicorn
        from sme.main import create_app
    except Exception as exc:
        print(f"BROWSER SMOKE: SKIP — optional dependency unavailable: {exc}")
        return 2

    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    app = create_app(testing=True, database_url="sqlite+pysqlite:///:memory:")
    app.state.allowed_hosts.add(f"127.0.0.1:{port}")
    app.state.allowed_origins.add(origin)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        if not wait_for_server(f"{origin}/health"):
            print("BROWSER SMOKE: FAIL — isolated test server did not become healthy")
            return 1
        executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        failures: list[str] = []
        with sync_playwright() as playwright:
            launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            if executable:
                launch_args["executable_path"] = executable
            browser = playwright.chromium.launch(**launch_args)
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                page = context.new_page()
                page_errors: list[str] = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(origin + "/", wait_until="networkidle", timeout=15000)
                page.wait_for_selector("#app h1", timeout=8000)
                if page.title() != "Smart Meter Explorer V2":
                    failures.append(f"unexpected document title: {page.title()!r}")
                if "Understand your usage" not in page.locator("#app").inner_text():
                    failures.append("fallback sign-in view did not render expected hero content")
                if page.locator(".pulse-line path").count() != 1:
                    failures.append("Pulse line graphic did not render exactly once")

                # OS-level reduced motion should reduce CSS animation duration to effectively zero.
                page.emulate_media(reduced_motion="reduce")
                duration = page.locator(".pulse-line path").evaluate("el => getComputedStyle(el).animationDuration")
                def seconds(value: str) -> float:
                    value = value.strip()
                    return float(value[:-2]) / 1000 if value.endswith("ms") else float(value[:-1])
                if seconds(duration.split(",")[0]) > 0.001:
                    failures.append(f"OS reduced-motion did not suppress pulse animation (duration={duration})")

                # App-level reduced-motion class is applied before the first render.
                context2 = browser.new_context(viewport={"width": 1280, "height": 900})
                context2.add_init_script("localStorage.setItem('sme.pulse.preferences.v1', JSON.stringify({soundEnabled:false, reducedMotion:true, calmMode:false}));")
                page2 = context2.new_page()
                page2.goto(origin + "/", wait_until="networkidle", timeout=15000)
                app_class = page2.locator("html").evaluate("el => el.classList.contains('reduced-motion')")
                app_animation = page2.locator(".pulse-line path").evaluate("el => getComputedStyle(el).animationName")
                if not app_class or app_animation != "none":
                    failures.append("saved app-level Reduce motion preference was not applied")
                if page2.evaluate("JSON.parse(localStorage.getItem('sme.pulse.preferences.v1')).soundEnabled") is not False:
                    failures.append("sound default/persisted preference was not off")

                # Check a representative set of phone/tablet/desktop widths for document overflow.
                for width in (360, 390, 768, 1280):
                    page.set_viewport_size({"width": width, "height": 900})
                    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                    if overflow:
                        failures.append(f"horizontal page overflow at viewport width {width}px")

                if page_errors:
                    failures.extend(f"uncaught browser exception: {error}" for error in page_errors)
                context2.close()
                context.close()
            finally:
                browser.close()
        if failures:
            print("BROWSER SMOKE: FAIL")
            for failure in failures:
                print(f" - {failure}")
            return 1
        print("BROWSER SMOKE: PASS")
        print(" - fallback UI rendered without uncaught JavaScript exceptions")
        print(" - OS and app-level reduced-motion preferences applied")
        print(" - sound remained disabled by default")
        print(" - no horizontal page overflow at 360/390/768/1280px")
        return 0
    except Exception as exc:
        message = str(exc)
        if "ERR_BLOCKED_BY_ADMINISTRATOR" in message:
            print("BROWSER SMOKE: BLOCKED — container browser policy prevented local page navigation")
            return 2
        if "Executable doesn't exist" in message or "playwright install" in message.lower():
            print("BROWSER SMOKE: SKIP — install a Playwright browser with `python -m playwright install chromium`")
            return 2
        print(f"BROWSER SMOKE: FAIL — {type(exc).__name__}: {message}")
        return 1
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
