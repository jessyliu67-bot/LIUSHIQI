"""Playwright smoke checks for the real local asset dashboard."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (320, 375, 390, 430, 768, 1024, 1440, 1920)


@pytest.fixture(scope="module")
def local_app(tmp_path_factory):
    data = tmp_path_factory.mktemp("bigbang-ui-data")
    (data / "uploads").mkdir()
    shutil.copy2(ROOT / "data" / "bigbang.sqlite3", data / "bigbang.sqlite3")
    shutil.copy2(ROOT / "data" / "ASSET_MANIFEST.json", data / "ASSET_MANIFEST.json")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env.update({
        "BIGBANG_DATA_DIR": str(data),
        "ADMIN_PASSWORD": "ci-ui-test-only",
        "SESSION_SECRET": "ci-ui-test-secret-" * 4,
        "BIGBANG_DESKTOP_MODE": "1",
        "BIGBANG_TEST_MODE": "1",
    })
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 45
    while time.time() < deadline:
        if process.poll() is not None:
            detail = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
            raise RuntimeError(f"BIG BANG local test server stopped early: {detail[-4000:]}")
        try:
            from urllib.request import urlopen
            with urlopen(url + "/api/health", timeout=1) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.25)
    else:
        process.terminate()
        raise RuntimeError("BIG BANG local test server did not become ready")
    yield url
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_asset_list_is_visible_and_responsive_at_required_widths(local_app):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": WIDTHS[0], "height": 900})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("console", lambda message: page_errors.append(message.text) if message.type == "error" else None)
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(local_app + "/platform-assets", wait_until="networkidle")
            page.locator("#records tr").first.wait_for(state="visible", timeout=15000)
            assert page.locator("#records tr").count() == 35
            assert page.locator("#records").inner_text().strip()
            assert page.locator("#message").inner_text().find("SHOPIFY") >= 0
            metrics = page.evaluate("""() => ({
                viewport: window.innerWidth,
                document: document.documentElement.scrollWidth,
                rows: document.querySelectorAll('#records tr').length,
                table: document.querySelector('#records').getBoundingClientRect().width
            })""")
            assert metrics["document"] <= metrics["viewport"], f"horizontal overflow at {width}px: {metrics}"
            assert metrics["rows"] > 0, f"empty store/product resource area at {width}px"
        browser.close()
        assert not page_errors, "Browser JavaScript errors: " + " | ".join(page_errors)
