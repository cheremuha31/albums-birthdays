from __future__ import annotations

import logging
import os
from datetime import date

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from album_analyzer.exporter import load_albums
from album_analyzer.models import AlbumListening

from .birthdays import calculate_upcoming_birthdays, format_birthday_message
from .storage import (
    DATA_DIR,
    iter_users,
    load_notification_log,
    load_user_albums,
    save_notification_log,
    save_user_albums,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_WITHIN_DAYS = 30
UPCOMING_NOTIFICATIONS = (7, 1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Пришлите JSON файл, созданный приложением albums-birthdays, и я напомню о днях рождения альбомов."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "1. С помощью приложения подготовьте файл albums.json.\n"
        "2. Отправьте файл этому боту.\n"
        "3. Используйте /upcoming [дней], чтобы посмотреть ближайшие события."
    )


def _summarize_albums(albums: list[AlbumListening]) -> str:
    total_minutes = sum(album.minutes for album in albums)
    with_dates = sum(1 for album in albums if album.release_date)
    return (
        f"Загружено {len(albums)} альбомов.\n"
        f"Общее время прослушивания: {int(total_minutes)} минут.\n"
        f"Есть дата релиза у {with_dates} альбомов."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document:
        return
    document = update.message.document
    if not document.file_name.endswith(".json"):
        await update.message.reply_text("Ожидаю JSON файл, созданный приложением.")
        return

    chat_id = update.message.chat_id
    file = await document.get_file()
    temp_path = DATA_DIR / f"{chat_id}_upload.json"
    await file.download_to_drive(custom_path=temp_path)
    try:
        albums = load_albums(temp_path)
    except Exception as exc:  # pragma: no cover - parsing guard
        LOGGER.exception("Failed to parse uploaded file from %s", chat_id)
        await update.message.reply_text(f"Не удалось прочитать файл: {exc}")
        temp_path.unlink(missing_ok=True)
        return

    save_user_albums(chat_id, albums)
    temp_path.unlink(missing_ok=True)
    await update.message.reply_text("Файл сохранён. " + _summarize_albums(albums))


async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    albums = load_user_albums(chat_id)
    if not albums:
        await update.message.reply_text("Сначала загрузите файл с альбомами.")
        return
    try:
        days = int(context.args[0]) if context.args else DEFAULT_WITHIN_DAYS
    except ValueError:
        days = DEFAULT_WITHIN_DAYS
    events = calculate_upcoming_birthdays(albums, within_days=days)
    if not events:
        await update.message.reply_text("В выбранный период праздников нет.")
        return
    messages = [format_birthday_message(event) for event in events]
    await update.message.reply_text("\n\n".join(messages))


async def _notify_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message: str) -> None:
    try:
        await context.bot.send_message(chat_id=chat_id, text=message)
    except Exception as exc:  # pragma: no cover - network errors
        LOGGER.warning("Failed to notify %s: %s", chat_id, exc)


async def send_daily_notifications(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = date.today()
    days_before = context.job.data.get("days_before", UPCOMING_NOTIFICATIONS) if context.job else UPCOMING_NOTIFICATIONS
    within_days = max(days_before + (0,))
    log = load_notification_log()
    changed = False
    for chat_id in iter_users():
        albums = load_user_albums(chat_id)
        if not albums:
            continue
        events = calculate_upcoming_birthdays(albums, today=today, within_days=within_days)
        for event in events:
            key_base = f"{chat_id}|{event.album.artist}|{event.album.album}|{event.next_date.year}"
            if event.days_until == 0:
                key = f"{key_base}|day"
                if log.get(key) == today.isoformat():
                    continue
                await _notify_user(context, chat_id, format_birthday_message(event))
                log[key] = today.isoformat()
                changed = True
            elif event.days_until in days_before:
                key = f"{key_base}|{event.days_until}"
                if log.get(key) == today.isoformat():
                    continue
                await _notify_user(context, chat_id, format_birthday_message(event))
                log[key] = today.isoformat()
                changed = True
    if changed:
        save_notification_log(log)


def build_application(token: str) -> Application:
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("upcoming", upcoming))
    application.add_handler(MessageHandler(filters.Document.FileExtension("json"), handle_document))
    application.job_queue.run_repeating(
        send_daily_notifications,
        interval=24 * 60 * 60,
        first=10,
        data={"days_before": UPCOMING_NOTIFICATIONS},
    )
    return application


def main() -> None:  # pragma: no cover - entry point
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")
    logging.basicConfig(level=logging.INFO)
    application = build_application(token)
    application.run_polling()


if __name__ == "__main__":  # pragma: no cover
    main()
