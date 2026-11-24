"""Open BIG BANG in the default Windows browser when its own backend is ready.

Launcher hotfix for V11.3.3: older build incorrectly expected health version 11.1.0.
This file does not alter database, configuration, templates, or policies.
"""
import json
import os
import sys
import time
import urllib.request
import webbrowser

HOME_URL = "http://127.0.0.1:8787/"
HEALTH_URL = "http://127.0.0.1:8787/api/health"
EXPECTED_VERSION = "11.4.0"


def expected_server(payload):
    return (
        isinstance(payload, dict)
        and payload.get("ok") is True
        and str(payload.get("version", "")) == EXPECTED_VERSION
    )


def open_homepage():
    # os.startfile opens the machine's configured default browser on Windows.
    if os.name == "nt":
        try:
            os.startfile(HOME_URL)
            return True
        except (OSError, AttributeError) as exc:
            print("Windows default-browser launch failed:", exc, flush=True)
    try:
        return bool(webbrowser.open(HOME_URL, new=2))
    except Exception as exc:
        print("Browser launch failed:", exc, flush=True)
        return False


def wait_and_open(attempts=120, delay=1):
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
                payload = json.load(response)
            if expected_server(payload):
                if open_homepage():
                    print("BIG BANG V11.4.0 browser opened.", flush=True)
                else:
                    print("Open this address manually: " + HOME_URL, flush=True)
                return True
            if isinstance(payload, dict) and payload.get("ok") and payload.get("version"):
                print("Different BIG BANG server version found: " + str(payload["version"]), flush=True)
                print("Close the old BIG BANG process and relaunch V11.4.0.", flush=True)
                return False
        except Exception:
            pass
        time.sleep(delay)
    print("BIG BANG did not become ready. Check the main server window.", flush=True)
    return False


if __name__ == "__main__":
    sys.exit(0 if wait_and_open() else 1)
