from __future__ import annotations

import json
import logging
from io import TextIOWrapper
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

from .models import AlbumListening

LOGGER = logging.getLogger(__name__)

SUPPORTED_JSON_SUFFIXES = (
    "endsong_",
    "Streaming_History_Audio",
    "StreamingHistory",
)


def _iter_json_streams(path: Path) -> Iterable[dict]:
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        yield entry
            else:
                LOGGER.debug("Ignoring non list JSON file %s", path)
        return

    if path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            for name in archive.namelist():
                lowered = name.lower()
                if not lowered.endswith(".json"):
                    continue
                if not any(suffix in lowered for suffix in SUPPORTED_JSON_SUFFIXES):
                    continue
                with archive.open(name) as handle:
                    wrapper = TextIOWrapper(handle, encoding="utf-8")
                    try:
                        data = json.load(wrapper)
                    except json.JSONDecodeError as exc:  # pragma: no cover - logging branch
                        LOGGER.warning("Failed to parse %s from %s: %s", name, path, exc)
                        continue
                    if isinstance(data, list):
                        for entry in data:
                            if isinstance(entry, dict):
                                yield entry
                    else:  # pragma: no cover - logging branch
                        LOGGER.debug("Ignoring non list JSON file %s inside %s", name, path)
    else:
        raise ValueError(f"Unsupported archive format: {path}")


def _extract_album_entry(entry: dict) -> tuple[str | None, str | None, str | None, float]:
    album = (
        entry.get("master_metadata_album_album_name")
        or entry.get("albumName")
        or entry.get("album")
        or entry.get("release_name")
    )
    artist = (
        entry.get("master_metadata_album_artist_name")
        or entry.get("artistName")
        or entry.get("artist")
    )
    track = (
        entry.get("master_metadata_track_name")
        or entry.get("trackName")
        or entry.get("track")
    )
    ms_played = (
        entry.get("ms_played")
        or entry.get("msPlayed")
        or entry.get("ms_played")
        or entry.get("ms_played")
    )
    minutes = float(ms_played or 0) / 60000.0
    return album, artist, track, minutes


def aggregate_archives(paths: Iterable[Path]) -> list[AlbumListening]:
    totals: dict[tuple[str, str], AlbumListening] = {}

    for path in paths:
        for entry in _iter_json_streams(path):
            album, artist, track, minutes = _extract_album_entry(entry)
            if not album or not artist or minutes <= 0:
                continue
            key = (album.strip(), artist.strip())
            if key not in totals:
                totals[key] = AlbumListening(album=key[0], artist=key[1], minutes=0.0)
            totals[key].minutes += minutes
            if track:
                totals[key].tracks.add(track)

    return sorted(totals.values(), key=lambda item: item.minutes, reverse=True)


def filter_by_minutes(albums: Iterable[AlbumListening], minimum_minutes: float) -> list[AlbumListening]:
    return [album for album in albums if album.minutes >= minimum_minutes]
