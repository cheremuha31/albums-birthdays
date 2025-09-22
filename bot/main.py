from __future__ import annotations

import logging
import os
from datetime import date, time, timezone
from typing import Any, Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
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
UPCOMING_DAY_PRESETS = (7, 30, 90)


def _get_upcoming_views(context: ContextTypes.DEFAULT_TYPE) -> Dict[int, Dict[str, Any]]:
    return context.user_data.setdefault("upcoming_views", {})


def _build_upcoming_message(view: Dict[str, Any]) -> str:
    days = view["days"]
    events = view["events"]
    index = view.get("index", 0)
    total = len(events)
    header = f"Период: {days} дн."
    if not events:
        return header + "\n\nВ этом диапазоне праздников нет."
    current = events[index]
    position = f"Запись {index + 1} из {total}."
    return f"{header}\n{position}\n\n{format_birthday_message(current)}"


def _build_upcoming_keyboard(view: Dict[str, Any]) -> InlineKeyboardMarkup:
    events = view["events"]
    index = view.get("index", 0)
    total = len(events)
    rows: list[list[InlineKeyboardButton]] = []

    if total:
        navigation: list[InlineKeyboardButton] = []
        if index > 0:
            navigation.append(InlineKeyboardButton("⬅️ Назад", callback_data="upcoming:prev"))
        navigation.append(InlineKeyboardButton(f"{index + 1}/{total}", callback_data="upcoming:noop"))
        if index < total - 1:
            navigation.append(InlineKeyboardButton("Вперёд ➡️", callback_data="upcoming:next"))
        rows.append(navigation)
    else:
        rows.append([InlineKeyboardButton("Нет событий", callback_data="upcoming:noop")])

    day_buttons = []
    for preset in UPCOMING_DAY_PRESETS:
        label = f"• {preset} дн." if preset == view["days"] else f"{preset} дн."
        day_buttons.append(InlineKeyboardButton(label, callback_data=f"upcoming:days:{preset}"))
    rows.append(day_buttons)

    rows.append([InlineKeyboardButton("Закрыть", callback_data="upcoming:close")])
    return InlineKeyboardMarkup(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Пришлите JSON файл, созданный приложением albums-birthdays, и я напомню о днях рождения альбомов."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "1. С помощью приложения подготовьте файл albums.json.\n"
        "2. Отправьте файл этому боту.\n"
        "3. Используйте /upcoming [дней], чтобы посмотреть ближайшие события и навигацию через кнопки."
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
    if not update.message:
        return
    chat_id = update.message.chat_id
    albums = load_user_albums(chat_id)
    if not albums:
        await update.message.reply_text("Сначала загрузите файл с альбомами.")
        return
    try:
        days = int(context.args[0]) if context.args else DEFAULT_WITHIN_DAYS
    except ValueError:
        days = DEFAULT_WITHIN_DAYS
    view: Dict[str, Any] = {"days": days, "events": calculate_upcoming_birthdays(albums, within_days=days), "index": 0}
    text = _build_upcoming_message(view)
    markup = _build_upcoming_keyboard(view)
    sent_message = await update.message.reply_text(text, reply_markup=markup)
    views = _get_upcoming_views(context)
    views[sent_message.message_id] = view
    # keep last few views to avoid unbounded growth
    if len(views) > 10:
        for message_id in list(views)[:-10]:
            views.pop(message_id, None)


async def handle_upcoming_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    parts = query.data.split(":")
    if not parts or parts[0] != "upcoming":
        await query.answer()
        return
    message = query.message
    if not message:
        await query.answer()
        return

    views = _get_upcoming_views(context)
    view = views.get(message.message_id)
    if not view:
        await query.answer("Список устарел, используйте /upcoming заново.", show_alert=True)
        return

    action = parts[1] if len(parts) > 1 else ""
    if action == "noop":
        await query.answer()
        return
    if action == "close":
        views.pop(message.message_id, None)
        await query.answer()
        try:
            await message.delete()
        except Exception:  # pragma: no cover - network issues
            await query.edit_message_reply_markup(reply_markup=None)
        return

    updated = False
    if action == "prev":
        if view["events"] and view["index"] > 0:
            view["index"] -= 1
            updated = True
        else:
            await query.answer("Это первая запись.")
            return
    elif action == "next":
        if view["events"] and view["index"] < len(view["events"]) - 1:
            view["index"] += 1
            updated = True
        else:
            await query.answer("Это последняя запись.")
            return
    elif action == "days" and len(parts) > 2:
        try:
            new_days = int(parts[2])
        except ValueError:
            await query.answer("Некорректный диапазон.", show_alert=True)
            return
        if new_days == view["days"]:
            await query.answer()
            return
        albums = load_user_albums(message.chat_id)
        if not albums:
            await query.answer("Сначала загрузите файл с альбомами.", show_alert=True)
            return
        view["days"] = new_days
        view["events"] = calculate_upcoming_birthdays(albums, within_days=new_days)
        view["index"] = 0
        updated = True
    else:
        await query.answer()
        return

    if updated:
        text = _build_upcoming_message(view)
        markup = _build_upcoming_keyboard(view)
        await query.edit_message_text(text=text, reply_markup=markup)
    await query.answer()


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
    application.add_handler(CallbackQueryHandler(handle_upcoming_callback, pattern=r"^upcoming:"))
    application.add_handler(MessageHandler(filters.Document.FileExtension("json"), handle_document))
    application.job_queue.run_daily(
        send_daily_notifications,
        time=time(hour=0, minute=0, tzinfo=timezone.utc),
        name="daily-birthday-check",
        data={"days_before": UPCOMING_NOTIFICATIONS},
    )
    application.job_queue.run_once(
        send_daily_notifications,
        when=10,
        name="initial-birthday-check",
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
