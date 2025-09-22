from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List

from album_analyzer.models import AlbumListening


@dataclass(slots=True)
class UpcomingBirthday:
    album: AlbumListening
    next_date: date
    age: int
    days_until: int


def _replace_year(source: date, year: int) -> date:
    try:
        return source.replace(year=year)
    except ValueError:
        # Handle February 29 releases by falling back to February 28
        if source.month == 2 and source.day == 29:
            return date(year, 2, 28)
        raise


def next_birthday(release_date: date, today: date | None = None) -> date:
    today = today or date.today()
    candidate = _replace_year(release_date, today.year)
    if candidate < today:
        candidate = _replace_year(release_date, today.year + 1)
    return candidate


def calculate_upcoming_birthdays(
    albums: Iterable[AlbumListening],
    today: date | None = None,
    within_days: int = 30,
) -> List[UpcomingBirthday]:
    today = today or date.today()
    upcoming: List[UpcomingBirthday] = []
    for album in albums:
        if not album.release_date:
            continue
        next_day = next_birthday(album.release_date, today)
        days_until = (next_day - today).days
        if days_until > within_days:
            continue
        age = next_day.year - album.release_date.year
        upcoming.append(UpcomingBirthday(album=album, next_date=next_day, age=age, days_until=days_until))
    upcoming.sort(key=lambda item: (item.days_until, item.album.artist, item.album.album))
    return upcoming


def format_birthday_message(event: UpcomingBirthday) -> str:
    if event.days_until == 0:
        prefix = "Сегодня день рождения альбома!"
    elif event.days_until == 1:
        prefix = "Завтра день рождения альбома"
    else:
        prefix = f"Через {event.days_until} дн. день рождения альбома"
    return (
        f"{prefix}\n"
        f"{event.album.artist} — {event.album.album}\n"
        f"Альбому исполнится {event.age} лет ({event.album.release_date.isoformat()})\n"
        f"Вы слушали {event.album.minutes:.0f} минут"
    )
