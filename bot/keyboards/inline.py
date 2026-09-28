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


def event_type_inline_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа мероприятия."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📚 Учебное", callback_data=f"event_type:{EventType.ACADEMIC.value}"),
        InlineKeyboardButton(text="🎉 Внеучебное", callback_data=f"event_type:{EventType.EXTRACURRICULAR.value}"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"))
    return builder.as_markup()


def application_review_keyboard(app_id: int, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура модерации заявки с пагинацией."""
    builder = InlineKeyboardBuilder()

    # Кнопки действий
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"rev_approve:{app_id}:{current_page}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rev_reject:{app_id}:{current_page}"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить баллы", callback_data=f"rev_edit:{app_id}:{current_page}")
    )

    # Навигация (пагинация)
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"rev_page:{current_page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"📄 {current_page + 1}/{total_pages}", callback_data="noop")
    )
    if current_page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="Вперед ▶️", callback_data=f"rev_page:{current_page + 1}")
        )
    builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Закрыть модерацию", callback_data="admin_menu_back"))
    return builder.as_markup()


def student_selection_keyboard(students: List[Student]) -> InlineKeyboardMarkup:
    """Клавиатура выбора студента из найденных при ручном начислении."""
    builder = InlineKeyboardBuilder()
    for s in students:
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {s.full_name} ({s.group_name})",
                callback_data=f"select_student:{s.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"))
    return builder.as_markup()


def cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Простая кнопка отмены в inline-виде."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"))
    return builder.as_markup()
