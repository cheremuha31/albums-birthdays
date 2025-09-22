"""Helper to bundle the web UI into standalone executables with PyInstaller."""
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


ENTRY_SCRIPTS = {
    "browser": "run_webapp.py",
    "desktop": "run_desktop.py",
}

DEFAULT_APP_NAMES = {
    "browser": "albums-json-web",
    "desktop": "albums-json-desktop",
}


def build(name: str, entry_script: Path, windowed: bool, clean: bool) -> Path:
    """Invoke PyInstaller and return a path to the built executable."""
    if pyinstaller_run is None:  # pragma: no cover - dependency is optional at runtime
        raise SystemExit(
            "PyInstaller is not installed. Install it first with `pip install pyinstaller`."
        ) from _IMPORT_ERROR

    if not entry_script.exists():  # pragma: no cover - sanity guard
        raise SystemExit(f"{entry_script.name} was not found. Make sure you run the script from the repo root.")

    args: list[str] = [
        str(entry_script),
        "--name",
        name,
        "--onefile",
    ]

    if entry_script.name == "run_desktop.py":
        # pywebview loads its platform backends dynamically, so we need to
        # tell PyInstaller to bundle them explicitly when building the desktop
        # executable. Otherwise the app launches without opening a window.
        args.extend(
            [
                "--hidden-import",
                "webview",
                "--collect-submodules",
                "webview",
                "--collect-data",
                "webview",
            ]
        )
    if windowed:
        args.append("--noconsole")
    if clean:
        args.append("--clean")

    pyinstaller_run(args)

    project_root = Path(__file__).resolve().parent
    executable = project_root / "dist" / (name + (".exe" if sys.platform.startswith("win") else ""))
    if not executable.exists():  # pragma: no cover - check for non-Windows name
        executable = project_root / "dist" / name
    return executable


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=sorted(ENTRY_SCRIPTS.keys()),
        default="browser",
        help=(
            "Type of executable to build: 'browser' launches the app in the system browser (default); "
            "'desktop' embeds the UI via pywebview."
        ),
    )
    parser.add_argument(
        "--name",
        help="Name of the generated executable (default depends on --mode)",
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
    project_root = Path(__file__).resolve().parent
    entry_script = project_root / ENTRY_SCRIPTS[args.mode]
    name = args.name or DEFAULT_APP_NAMES[args.mode]

    executable_path = build(
        name=name,
        entry_script=entry_script,
        windowed=not args.console,
        clean=args.clean,
    )
    message = f"Executable built at: {executable_path}"
    if executable_path.exists():
        size = executable_path.stat().st_size
        message += f" (size: {size / (1024 * 1024):.1f} MiB)"
    print(message)


if __name__ == "__main__":  # pragma: no cover - CLI helper
    main()
