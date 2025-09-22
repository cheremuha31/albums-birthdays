"""Entry point for running the web UI in an embedded desktop window."""

from __future__ import annotations

import socket
import threading
import time
from contextlib import suppress

from album_analyzer.webapp import create_app

try:  # pragma: no cover - optional dependency for desktop mode
    from werkzeug.serving import make_server
except ModuleNotFoundError as exc:  # pragma: no cover - Werkzeug is provided by Flask
    raise SystemExit("Flask/Werkzeug is required to run the desktop application.") from exc


def _import_pywebview():
    """Import ``pywebview`` lazily and provide a helpful error if it is missing."""

    try:  # pragma: no cover - executed only when running desktop mode manually
        import webview  # type: ignore[import]
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency is optional in tests
        raise SystemExit(
            "pywebview is not installed. Install it with `pip install pywebview` to use the desktop UI."
        ) from exc
    return webview


class _FlaskServer(threading.Thread):
    """Run the Flask application in a background thread."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._server = make_server("127.0.0.1", 0, create_app(), threaded=True)
        self._server.timeout = 1
        self.port = self._server.server_port

    def run(self) -> None:  # pragma: no cover - relies on Flask internals
        self._server.serve_forever()

    def shutdown(self) -> None:  # pragma: no cover - depends on Werkzeug internals
        with suppress(Exception):
            self._server.shutdown()
        with suppress(Exception):
            self._server.server_close()


def _wait_for_server(port: int, timeout: float = 10.0) -> None:
    """Block until the background Flask server starts accepting connections."""

    deadline = time.time() + timeout
    while time.time() < deadline:
        with suppress(OSError):
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        time.sleep(0.1)
    raise RuntimeError("Не удалось запустить локальный сервер Flask.")


def main() -> None:
    """Run the web UI inside a lightweight desktop window."""

    webview = _import_pywebview()

    server = _FlaskServer()
    server.start()

    try:
        _wait_for_server(server.port)
    except Exception:
        server.shutdown()
        raise

    window_title = "albums-birthdays — подготовка JSON"
    window_url = f"http://127.0.0.1:{server.port}"

    try:
        webview.create_window(window_title, window_url, width=1024, height=720, resizable=True)
        webview.start()
    finally:
        server.shutdown()
        server.join(timeout=5)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
