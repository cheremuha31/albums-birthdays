"""Entry point for bundling the web UI into a standalone executable."""
from __future__ import annotations

import threading
import webbrowser

from album_analyzer.webapp import main as webapp_main


def _open_browser() -> None:
    """Open the local application page in the default browser."""
    try:
        webbrowser.open("http://127.0.0.1:5000", new=0, autoraise=True)
    except Exception:
        # Browser availability is platform-specific; ignore any errors here.
        pass


def main() -> None:
    """Start the web application and open the browser window."""
    threading.Timer(1.0, _open_browser).start()
    webapp_main()


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
