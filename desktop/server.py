"""Manages the embedded Flask subprocess that serves the dashboard + graph views."""

from __future__ import annotations

import atexit
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_PY = REPO_ROOT / "run.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FlaskServer:
    """Spawn `python run.py` on a free port and wait for it to accept requests."""

    def __init__(self):
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self._proc: subprocess.Popen | None = None

    def start(self, timeout: float = 30.0) -> None:
        env = {
            **_inherit_env(),
            "FLASK_RUN_HOST": "127.0.0.1",
            "FLASK_RUN_PORT": str(self.port),
            "DARK_INTEL_PORT": str(self.port),
        }
        self._proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                # Bind to a chosen port without depending on run.py's flask.run() args.
                "from app import create_app; "
                "import os; "
                "create_app().run("
                "host='127.0.0.1', "
                "port=int(os.environ['DARK_INTEL_PORT']), "
                "debug=False, use_reloader=False)",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        atexit.register(self.stop)
        self._wait_ready(timeout)

    def _wait_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{self.url}/api/analyses", timeout=1) as r:
                    if r.status == 200:
                        return
            except Exception:
                pass
            if self._proc and self._proc.poll() is not None:
                raise RuntimeError("Embedded Flask server exited before becoming ready.")
            time.sleep(0.25)
        self.stop()
        raise TimeoutError("Embedded Flask server didn't respond in time.")

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None


def _inherit_env() -> dict:
    import os

    return dict(os.environ)
