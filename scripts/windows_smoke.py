#!/usr/bin/env python3
"""Start a built Windows package and verify the local health endpoint."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from urllib.request import urlopen


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/windows_smoke.py path/to/BIG_BANG.exe")
        return 2
    executable = os.path.abspath(sys.argv[1])
    if not os.path.isfile(executable):
        raise SystemExit(f"Missing Windows executable: {executable}")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env.update({"BIGBANG_PORT": str(port), "BIGBANG_AUTO_OPEN_BROWSER": "0"})
    process = subprocess.Popen([executable], cwd=os.path.dirname(executable), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + 90
    try:
        while time.time() < deadline:
            if process.poll() is not None:
                output = process.stdout.read().decode("utf-8", "replace") if process.stdout else ""
                raise RuntimeError(f"Windows package exited before health check ({process.returncode}):\n{output[-6000:]}")
            try:
                with urlopen(url, timeout=2) as response:
                    body = response.read().decode("utf-8", "replace")
                    if response.status == 200 and '"V35"' in body and '"stores":300' in body:
                        print(f"PASS Windows executable started: {body}")
                        return 0
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("Windows package health endpoint did not become ready within 90 seconds")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
