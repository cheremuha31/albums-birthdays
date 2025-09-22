from __future__ import annotations

from typing import TYPE_CHECKING

from .exporter import export_albums, load_albums
from .models import AlbumListening
from .parser import aggregate_archives, filter_by_minutes
from .release_date import enrich_with_release_dates

if TYPE_CHECKING:  # pragma: no cover - import for type checkers only
    from .cli import app as _cli_app

    app = _cli_app

__all__ = [
    "AlbumListening",
    "aggregate_archives",
    "filter_by_minutes",
    "export_albums",
    "load_albums",
    "enrich_with_release_dates",
    "app",
]


def __getattr__(name: str) -> object:
    if name == "app":
        from .cli import app as cli_app

        return cli_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:  # pragma: no cover - trivial delegation
    return sorted(list(__all__))
