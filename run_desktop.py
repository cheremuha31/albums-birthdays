"""Entry point for running the web UI in an embedded desktop window."""

from __future__ import annotations

import socket
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

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


class _DesktopApi:
    """Expose helpers to the embedded browser window."""

    def __init__(self, webview_module: Any) -> None:
        self._webview = webview_module
        self._window: Any | None = None

    def attach_window(self, window: Any) -> None:
        """Remember the pywebview window instance once it is created."""

        self._window = window

    def _prompt_with_pywebview(
        self, filename: str
    ) -> tuple[Path | None, bool, str | None]:
        """Try to let pywebview open a save dialog."""

        window = self._window
        if window is None:
            return None, False, "Окно ещё не готово."

        try:  # pragma: no cover - depends on GUI backend
            selection = window.create_file_dialog(
                self._webview.SAVE_DIALOG,
                save_filename=filename,
                file_types=("JSON файл (*.json)", "Все файлы (*.*)"),
            )
        except Exception as exc:  # pragma: no cover - backend specific
            return None, False, f"pywebview: {exc}"

        if not selection:
            return None, True, None

        if isinstance(selection, (list, tuple)):
            destination = selection[0]
        else:
            destination = selection

        if not destination:
            return None, True, None

        return Path(destination), False, None

    def _prompt_with_tkinter(
        self, filename: str
    ) -> tuple[Path | None, bool, str | None]:
        """Fallback to a tkinter-based save dialog if available."""

        try:  # pragma: no cover - optional dependency at runtime
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:  # pragma: no cover - depends on platform availability
            return None, False, f"tkinter: {exc}"

        try:
            root = tk.Tk()
        except Exception as exc:  # pragma: no cover - depends on platform availability
            return None, False, f"tkinter: {exc}"

        selection: str | tuple[str, ...] | None = None

        try:
            root.withdraw()
            try:
                root.update_idletasks()
            except Exception:  # pragma: no cover - best effort to avoid focus issues
                pass
            try:
                root.attributes("-topmost", True)
            except Exception:  # pragma: no cover - platform dependent
                pass

            selection = filedialog.asksaveasfilename(
                title="Сохранить файл",
                defaultextension=".json",
                initialfile=filename,
                filetypes=[("JSON файл (*.json)", "*.json"), ("Все файлы (*.*)", "*.*")],
            )
        except Exception as exc:  # pragma: no cover - UI toolkit specific
            return None, False, f"tkinter: {exc}"
        finally:
            try:
                root.destroy()
            except Exception:  # pragma: no cover - platform dependent cleanup
                pass

        if not selection:
            return None, True, None

        if isinstance(selection, (tuple, list)):
            destination = selection[0]
        else:
            destination = selection

        if not destination:
            return None, True, None

        return Path(destination), False, None

    def save_albums_json(self, filename: str, content: str) -> dict[str, str]:
        """Prompt the user to save the generated JSON file to disk."""

        errors: list[str] = []

        prompt_order = []
        if sys.platform.startswith("win"):
            prompt_order.extend(
                [
                    lambda: self._prompt_with_tkinter(filename),
                    lambda: self._prompt_with_pywebview(filename),
                ]
            )
        else:
            prompt_order.extend(
                [
                    lambda: self._prompt_with_pywebview(filename),
                    lambda: self._prompt_with_tkinter(filename),
                ]
            )

        for prompt in prompt_order:
            destination, cancelled, error = prompt()
            if error:
                errors.append(error)
                continue

            if destination is not None:
                try:
                    destination.write_text(content, encoding="utf-8")
                except OSError as exc:  # pragma: no cover - filesystem specific
                    errors.append(str(exc))
                    continue
                return {"status": "saved"}

            if cancelled:
                return {"status": "cancelled"}

        if errors:
            # Deduplicate errors while keeping order for readability.
            seen: set[str] = set()
            unique_errors = []
            for message in errors:
                if message and message not in seen:
                    seen.add(message)
                    unique_errors.append(message)
            return {"status": "error", "message": "; ".join(unique_errors)}

        return {"status": "error", "message": "Не удалось сохранить файл."}


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
    api = _DesktopApi(webview)

    try:
        window = webview.create_window(
            window_title,
            window_url,
            width=1024,
            height=720,
            resizable=True,
            js_api=api,
        )
        api.attach_window(window)
        webview.start()
    finally:
        server.shutdown()
        server.join(timeout=5)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
