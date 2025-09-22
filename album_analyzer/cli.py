from __future__ import annotations

from pathlib import Path
from typing import List

import typer

from .exporter import export_albums
from .parser import aggregate_archives, filter_by_minutes
from .release_date import enrich_with_release_dates

app = typer.Typer(help="Utility for preparing album listening statistics")


@app.command()
def export(
    archives: List[Path] = typer.Argument(..., exists=True, readable=True, help="ZIP or JSON files with streaming history"),
    output: Path = typer.Option(Path("albums.json"), "--output", "-o", help="Where to write filtered albums"),
    minimum_minutes: float = typer.Option(60.0, "--min-minutes", "-m", help="Minimum minutes listened per album"),
    fetch_release_dates: bool = typer.Option(True, "--fetch-release-dates/--no-fetch-release-dates", help="Fetch release dates from MusicBrainz"),
    pause: float = typer.Option(1.1, help="Delay between MusicBrainz requests"),
) -> None:
    """Aggregate streaming history and export albums over the threshold."""

    albums = aggregate_archives(archives)
    filtered = filter_by_minutes(albums, minimum_minutes)
    if fetch_release_dates:
        filtered = enrich_with_release_dates(filtered, pause_seconds=pause)
    export_albums(filtered, output)
    typer.echo(f"Saved {len(filtered)} albums to {output}")


if __name__ == "__main__":  # pragma: no cover
    app()
