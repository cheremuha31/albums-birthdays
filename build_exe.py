"""Helper to bundle the web UI into a standalone executable with PyInstaller."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PyInstaller.__main__ import run as pyinstaller_run
except ModuleNotFoundError as exc:  # pragma: no cover - guard for missing dependency
    pyinstaller_run = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


DEFAULT_APP_NAME = "albums-json-web"


def build(name: str, windowed: bool, clean: bool) -> Path:
    """Invoke PyInstaller and return a path to the built executable."""
    if pyinstaller_run is None:  # pragma: no cover - dependency is optional at runtime
        raise SystemExit(
            "PyInstaller is not installed. Install it first with `pip install pyinstaller`."
        ) from _IMPORT_ERROR

    project_root = Path(__file__).resolve().parent
    entry_script = project_root / "run_webapp.py"
    if not entry_script.exists():  # pragma: no cover - sanity guard
        raise SystemExit("run_webapp.py was not found. Make sure you run the script from the repo root.")

    args: list[str] = [
        str(entry_script),
        "--name",
        name,
        "--onefile",
    ]
    if windowed:
        args.append("--noconsole")
    if clean:
        args.append("--clean")

    pyinstaller_run(args)

    executable = project_root / "dist" / (name + (".exe" if sys.platform.startswith("win") else ""))
    if not executable.exists():  # pragma: no cover - check for non-Windows name
        executable = project_root / "dist" / name
    return executable


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--name",
        default=DEFAULT_APP_NAME,
        help="Name of the generated executable (default: %(default)s)",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Keep the console window visible (only relevant on Windows).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove cached build data before running PyInstaller.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    executable_path = build(name=args.name, windowed=not args.console, clean=args.clean)
    message = f"Executable built at: {executable_path}"
    if executable_path.exists():
        size = executable_path.stat().st_size
        message += f" (size: {size / (1024 * 1024):.1f} MiB)"
    print(message)


if __name__ == "__main__":  # pragma: no cover - CLI helper
    main()
