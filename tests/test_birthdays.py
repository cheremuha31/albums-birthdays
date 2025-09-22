from datetime import date

from bot.birthdays import calculate_upcoming_birthdays, format_birthday_message, next_birthday
from album_analyzer.models import AlbumListening


def test_next_birthday_handles_past_dates() -> None:
    release = date(2020, 5, 1)
    today = date(2024, 6, 1)
    upcoming = next_birthday(release, today)
    assert upcoming == date(2025, 5, 1)


def test_calculate_upcoming_birthdays() -> None:
    albums = [
        AlbumListening(album="Album", artist="Artist", minutes=60, release_date=date(2020, 6, 10)),
        AlbumListening(album="Far", artist="Artist", minutes=10, release_date=date(2010, 12, 31)),
    ]
    today = date(2024, 6, 1)
    events = calculate_upcoming_birthdays(albums, today=today, within_days=15)
    assert len(events) == 1
    assert events[0].next_date == date(2024, 6, 10)
    message = format_birthday_message(events[0])
    assert "Album" in message
    assert "Artist" in message
