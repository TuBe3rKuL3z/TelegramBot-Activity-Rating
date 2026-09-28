from typing import List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import config
from bot.database.models import ApplicationRole, Event, EventType, Student


def events_inline_keyboard(events: List[Event]) -> InlineKeyboardMarkup:
    """Генерация списка активных мероприятий для выбора."""
    builder = InlineKeyboardBuilder()
    for event in events:
        date_str = event.event_date.strftime("%d.%m")
        btn_text = f"📅 {event.title} ({date_str})"
        builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"event:{event.id}"))

    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"))
    return builder.as_markup()


def roles_inline_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора роли на мероприятии с указанием баллов."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🙋 Участник (+{config.POINTS_PARTICIPANT} б.)",
            callback_data=f"role:{ApplicationRole.PARTICIPANT.value}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🤝 Помощник (+{config.POINTS_HELPER} б.)",
            callback_data=f"role:{ApplicationRole.HELPER.value}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"👑 Организатор (+{config.POINTS_ORGANIZER} б.)",
            callback_data=f"role:{ApplicationRole.ORGANIZER.value}",
        )
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"))
    return builder.as_markup()


def confirm_application_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения подачи заявки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить заявку", callback_data="app:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
    )
    return builder.as_markup()


def cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Простая кнопка отмены в inline-виде."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"))
    return builder.as_markup()
