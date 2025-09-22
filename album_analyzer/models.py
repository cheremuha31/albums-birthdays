from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(slots=True)
class AlbumListening:
    """Aggregated information about how long a user listened to an album."""

    album: str
    artist: str
    minutes: float
    release_date: Optional[date] = None
    musicbrainz_id: Optional[str] = None
    tracks: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "album": self.album,
            "artist": self.artist,
            "minutes_listened": round(self.minutes, 2),
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "musicbrainz_id": self.musicbrainz_id,
            "tracks": sorted(self.tracks),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AlbumListening":
        release_date: Optional[date]
        if data.get("release_date"):
            release_date = date.fromisoformat(data["release_date"])
        else:
            release_date = None
        return cls(
            album=data["album"],
            artist=data["artist"],
            minutes=float(data["minutes_listened"]),
            release_date=release_date,
            musicbrainz_id=data.get("musicbrainz_id"),
            tracks=set(data.get("tracks", [])),
        )
