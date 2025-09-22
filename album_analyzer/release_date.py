from __future__ import annotations

import logging
import time
from datetime import date
from typing import Iterable, Optional

import requests

from .models import AlbumListening

LOGGER = logging.getLogger(__name__)

MUSICBRAINZ_ENDPOINT = "https://musicbrainz.org/ws/2/release-group/"
USER_AGENT = "AlbumBirthdays/1.0 (example@example.com)"
_CACHE: dict[tuple[str, str], tuple[Optional[str], Optional[date]]] = {}


def _parse_release_date(raw: str | None) -> Optional[date]:
    if not raw:
        return None
    parts = raw.split("-")
    try:
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        if len(parts) == 2:
            return date(int(parts[0]), int(parts[1]), 1)
        if len(parts) == 1:
            return date(int(parts[0]), 1, 1)
    except ValueError:  # pragma: no cover - guard against unexpected data
        LOGGER.debug("Unable to parse release date %s", raw)
    return None


def lookup_release(album: str, artist: str, session: requests.Session | None = None) -> tuple[Optional[str], Optional[date]]:
    key = (album.lower(), artist.lower())
    if key in _CACHE:
        return _CACHE[key]

    params = {
        "fmt": "json",
        "limit": 5,
        "query": f'release:"{album}" AND artist:"{artist}"',
    }

    session = session or requests.Session()
    response = session.get(
        MUSICBRAINZ_ENDPOINT,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    best_id: Optional[str] = None
    best_date: Optional[date] = None
    for item in payload.get("release-groups", []):
        current_date = _parse_release_date(item.get("first-release-date"))
        if current_date and (not best_date or current_date < best_date):
            best_date = current_date
            best_id = item.get("id")

    _CACHE[key] = (best_id, best_date)
    return _CACHE[key]


def enrich_with_release_dates(
    albums: Iterable[AlbumListening],
    pause_seconds: float = 1.1,
    session: requests.Session | None = None,
) -> list[AlbumListening]:
    enriched: list[AlbumListening] = []
    album_list = list(albums)
    for index, album in enumerate(album_list):
        if album.release_date:
            enriched.append(album)
            continue
        try:
            musicbrainz_id, release_date = lookup_release(album.album, album.artist, session=session)
        except requests.RequestException as exc:  # pragma: no cover - network failure
            LOGGER.warning("Failed to fetch release date for %s - %s: %s", album.artist, album.album, exc)
            enriched.append(album)
            continue
        if release_date:
            album.release_date = release_date
        if musicbrainz_id:
            album.musicbrainz_id = musicbrainz_id
        enriched.append(album)
        if pause_seconds and index < len(album_list) - 1:
            time.sleep(pause_seconds)
    return enriched
