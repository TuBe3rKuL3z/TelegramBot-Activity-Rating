from typing import List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import config
from bot.database.models import ApplicationRole, Event
from bot.keyboards.callbacks import EventAction, MenuNav


def main_menu_inline_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Главное инлайн-меню бота."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📋 Мероприятия",
            callback_data=MenuNav(menu="events", page=1).pack(),
        ),
        InlineKeyboardButton(
            text="🏆 Топ рейтинга",
            callback_data=MenuNav(menu="top", page=1).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="👤 Мой профиль",
            callback_data=MenuNav(menu="profile").pack(),
        ),
        InlineKeyboardButton(
            text="ℹ️ Правила",
            callback_data=MenuNav(menu="rules").pack(),
        ),
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(
                text="⚙️ Панель администратора",
                callback_data=MenuNav(menu="admin").pack(),
            )
        )
    return builder.as_markup()


def events_list_inline_keyboard(
    events: List[Event],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Клавиатура со списком активных мероприятий и пагинацией."""
    builder = InlineKeyboardBuilder()

    for event in events:
        date_str = event.event_date.strftime("%d.%m")
        btn_text = f"📅 {event.title} ({date_str})"
        builder.row(
            InlineKeyboardButton(
                text=btn_text,
                callback_data=MenuNav(menu="event_detail", item_id=event.id, page=page).pack(),
            )
        )

    # Строка пагинации при наличии нескольких страниц
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=MenuNav(menu="events", page=page - 1).pack(),
                )
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⛔",
                    callback_data=MenuNav(menu="noop").pack(),
                )
            )

        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page}/{total_pages}",
                callback_data=MenuNav(menu="noop").pack(),
            )
        )

        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ▶️",
                    callback_data=MenuNav(menu="events", page=page + 1).pack(),
                )
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⛔",
                    callback_data=MenuNav(menu="noop").pack(),
                )
            )

        builder.row(*nav_buttons)

    # Кнопка возврата в главное меню
    builder.row(
        InlineKeyboardButton(
            text="« В главное меню",
            callback_data=MenuNav(menu="main").pack(),
        )
    )
    return builder.as_markup()


def event_detail_inline_keyboard(
    event_id: int,
    page: int,
    has_applied: bool,
    is_active: bool,
) -> InlineKeyboardMarkup:
    """Клавиатура детальной карточки мероприятия."""
    builder = InlineKeyboardBuilder()

    if is_active and not has_applied:
        builder.row(
            InlineKeyboardButton(
                text="🎯 Отметить участие",
                callback_data=EventAction(action="choose_role", event_id=event_id, page=page).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="« Назад к мероприятиям",
            callback_data=MenuNav(menu="events", page=page).pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data=MenuNav(menu="main").pack(),
        ),
    )
    return builder.as_markup()


def event_roles_inline_keyboard(event_id: int, page: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора роли для участия в мероприятии."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🙋 Участник (+{config.POINTS_PARTICIPANT} б.)",
            callback_data=EventAction(
                action="confirm",
                event_id=event_id,
                role=ApplicationRole.PARTICIPANT.value,
                page=page,
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🤝 Помощник (+{config.POINTS_HELPER} б.)",
            callback_data=EventAction(
                action="confirm",
                event_id=event_id,
                role=ApplicationRole.HELPER.value,
                page=page,
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"👑 Организатор (+{config.POINTS_ORGANIZER} б.)",
            callback_data=EventAction(
                action="confirm",
                event_id=event_id,
                role=ApplicationRole.ORGANIZER.value,
                page=page,
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="« Назад к мероприятию",
            callback_data=MenuNav(menu="event_detail", item_id=event_id, page=page).pack(),
        )
    )
    return builder.as_markup()


def event_confirm_inline_keyboard(event_id: int, role: str, page: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения отправки заявки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Отправить заявку",
            callback_data=EventAction(
                action="submit",
                event_id=event_id,
                role=role,
                page=page,
            ).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=MenuNav(menu="event_detail", item_id=event_id, page=page).pack(),
        ),
    )
    return builder.as_markup()


def application_submitted_inline_keyboard(page: int) -> InlineKeyboardMarkup:
    """Клавиатура после успешной подачи заявки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📋 К мероприятиям",
            callback_data=MenuNav(menu="events", page=page).pack(),
        ),
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data=MenuNav(menu="main").pack(),
        ),
    )
    return builder.as_markup()


def top_students_inline_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура рейтинга студентов с пагинацией."""
    builder = InlineKeyboardBuilder()

    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=MenuNav(menu="top", page=page - 1).pack(),
                )
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⛔",
                    callback_data=MenuNav(menu="noop").pack(),
                )
            )

        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page}/{total_pages}",
                callback_data=MenuNav(menu="noop").pack(),
            )
        )

        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ▶️",
                    callback_data=MenuNav(menu="top", page=page + 1).pack(),
                )
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⛔",
                    callback_data=MenuNav(menu="noop").pack(),
                )
            )

        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(
            text="« В главное меню",
            callback_data=MenuNav(menu="main").pack(),
        )
    )
    return builder.as_markup()


def profile_inline_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура профиля с кнопкой обновления данных и возврата."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data=MenuNav(menu="profile").pack(),
        ),
        InlineKeyboardButton(
            text="« В главное меню",
            callback_data=MenuNav(menu="main").pack(),
        ),
    )
    return builder.as_markup()


def rules_inline_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура раздела правил с кнопкой возврата."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="« В главное меню",
            callback_data=MenuNav(menu="main").pack(),
        )
    )
    return builder.as_markup()
