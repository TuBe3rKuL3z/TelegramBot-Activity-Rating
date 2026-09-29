import html
from typing import Any, Dict, List, Optional, Tuple
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import config
from bot.database.models import ApplicationRole, Event, Student
from bot.database.queries import (
    create_application,
    get_event_by_id,
    get_existing_application,
    get_paginated_active_events,
    get_paginated_top_students,
    get_student_by_id,
    get_student_by_telegram_id,
    get_student_rank_and_stats,
)
from bot.keyboards.callbacks import EventAction, MenuNav
from bot.keyboards.menu_inline import (
    application_submitted_inline_keyboard,
    event_confirm_inline_keyboard,
    event_detail_inline_keyboard,
    event_roles_inline_keyboard,
    events_list_inline_keyboard,
    main_menu_inline_keyboard,
    profile_inline_keyboard,
    rules_inline_keyboard,
    top_students_inline_keyboard,
)

router = Router(name="menu_router")


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ БЕЗОПАСНОГО РЕДАКТИРОВАНИЯ
# ==========================================

async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """
    Безопасное редактирование сообщения в рамках single-message UI.
    Перехватывает ошибку TelegramBadRequest ('message is not modified').
    """
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    except TelegramBadRequest as exc:
        err_msg = str(exc).lower()
        if "message is not modified" in err_msg:
            # Контент сообщения и разметка не изменились — ничего не делаем
            pass
        elif "message to edit not found" in err_msg:
            # Сообщение было удалено пользователем — отправляем новое
            await callback.message.answer(
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        else:
            raise


# ==========================================
# РЕНДЕРЕРЫ ЭКРАНОВ МЕНЮ
# ==========================================

def render_main_menu_screen(student: Student, is_admin: bool) -> Tuple[str, InlineKeyboardMarkup]:
    """Экран: Главное меню."""
    safe_name = html.escape(student.full_name)
    safe_group = html.escape(student.group_name)

    text = (
        "🏛 <b>Главное меню учёта активности</b>\n\n"
        f"👋 Привет, <b>{safe_name}</b>!\n"
        f"👥 Группа: <code>{safe_group}</code>\n"
        f"⭐ Ваш рейтинг: <b>{student.total_points}</b> баллов\n\n"
        "<i>Используйте кнопки ниже для навигации. Все действия и просмотр "
        "происходят прямо в этом сообщении без лишних уведомлений.</i>"
    )
    markup = main_menu_inline_keyboard(is_admin=is_admin)
    return text, markup


async def render_events_list_screen(
    session: AsyncSession,
    page: int,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Экран: Список активных мероприятий с пагинацией."""
    events, total_count, total_pages = await get_paginated_active_events(
        session=session,
        page=page,
        page_size=4,
    )

    if not events:
        text = (
            "📋 <b>Список мероприятий</b>\n\n"
            "📍 <i>В данный момент нет открытых мероприятий для регистрации.\n"
            "Следите за обновлениями или обратитесь к куратору!</i>"
        )
        markup = events_list_inline_keyboard(events=[], page=1, total_pages=1)
        return text, markup

    text = (
        f"📋 <b>Список мероприятий</b> (Стр. {page} из {total_pages})\n"
        f"Всего открытых событий: <b>{total_count}</b>\n\n"
        "<i>Нажмите на мероприятие для просмотра подробностей и записи:</i>"
    )
    markup = events_list_inline_keyboard(events=events, page=page, total_pages=total_pages)
    return text, markup


async def render_event_detail_screen(
    session: AsyncSession,
    student: Student,
    event_id: int,
    page: int,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Экран: Карточка мероприятия с кнопкой подачи заявки."""
    event = await get_event_by_id(session, event_id)
    if not event:
        text = "⚠️ <i>Мероприятие не найдено или было удалено.</i>"
        markup = events_list_inline_keyboard(events=[], page=page, total_pages=1)
        return text, markup

    existing_app = await get_existing_application(session, student.id, event.id)
    safe_title = html.escape(event.title)
    date_str = event.event_date.strftime("%d.%m.%Y")
    status_str = "🟢 Активно для записи" if event.is_active else "🔴 Завершено"

    app_block = ""
    if existing_app:
        app_block = (
            "\n📌 <b>Ваша заявка:</b>\n"
            f"• Роль: <b>{existing_app.role.label()}</b>\n"
            f"• Статус: <b>{existing_app.status.label()}</b>\n"
            f"• Баллы: <b>+{existing_app.points_calculated}</b>\n"
        )

    text = (
        f"🎪 <b>{safe_title}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Дата проведения:</b> {date_str}\n"
        f"📂 <b>Направление:</b> {event.event_type.label()}\n"
        f"Статус: {status_str}\n\n"
        "⭐ <b>Баллы за участие:</b>\n"
        f"• 🙋 Участник: <b>+{config.POINTS_PARTICIPANT}</b> б.\n"
        f"• 🤝 Помощник / Волонтер: <b>+{config.POINTS_HELPER}</b> б.\n"
        f"• 👑 Организатор: <b>+{config.POINTS_ORGANIZER}</b> б.\n"
        f"{app_block}"
    )

    markup = event_detail_inline_keyboard(
        event_id=event.id,
        page=page,
        has_applied=bool(existing_app),
        is_active=event.is_active,
    )
    return text, markup


async def render_top_students_screen(
    session: AsyncSession,
    current_student: Student,
    page: int,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Экран: Топ рейтинга студентов с пагинацией."""
    page_size = 5
    students, total_count, total_pages = await get_paginated_top_students(
        session=session,
        page=page,
        page_size=page_size,
    )
    stats = await get_student_rank_and_stats(session, current_student.id)

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []

    start_idx = (page - 1) * page_size + 1
    for i, s in enumerate(students, start=start_idx):
        badge = medals.get(i, f"{i}.")
        is_me = " <b>(Вы)</b>" if s.id == current_student.id else ""
        safe_name = html.escape(s.full_name)
        safe_group = html.escape(s.group_name)
        lines.append(
            f"{badge} <b>{safe_name}</b> (<code>{safe_group}</code>) — <code>{s.total_points} б.</code>{is_me}"
        )

    lines_str = "\n".join(lines) if lines else "<i>Рейтинговая таблица пуста.</i>"

    text = (
        f"🏆 <b>Топ студентов по активности</b> (Стр. {page}/{total_pages})\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{lines_str}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Ваша позиция: <b>#{stats['rank']}</b> из {stats['total_students']} "
        f"(<code>{current_student.total_points} б.</code>)"
    )
    markup = top_students_inline_keyboard(page=page, total_pages=total_pages)
    return text, markup


async def render_profile_screen(
    session: AsyncSession,
    student_id: int,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Экран: Личный профиль студента с историей операций."""
    student = await get_student_by_id(session, student_id)
    if not student:
        return "⚠️ <i>Профиль не найден.</i>", profile_inline_keyboard()

    stats = await get_student_rank_and_stats(session, student.id)

    history_lines = []
    if student.points_history:
        for item in student.points_history[:4]:
            sign = "+" if item.amount > 0 else ""
            date_str = item.created_at.strftime("%d.%m")
            safe_reason = html.escape(item.reason)
            history_lines.append(
                f"• <code>{date_str}</code>: <b>{sign}{item.amount} б.</b> — {safe_reason}"
            )
    else:
        history_lines.append("• <i>Начислений пока не зафиксировано.</i>")

    history_text = "\n".join(history_lines)
    safe_name = html.escape(student.full_name)
    safe_group = html.escape(student.group_name)

    text = (
        "👤 <b>Личный профиль студента</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"ФИО: <b>{safe_name}</b>\n"
        f"Группа: <code>{safe_group}</code>\n"
        f"Telegram ID: <code>{student.telegram_id}</code>\n\n"
        f"⭐ <b>Текущий баланс:</b> <code>{student.total_points}</code> баллов\n"
        f"🏅 <b>Место в рейтинге:</b> <code>#{stats['rank']}</code> из {stats['total_students']}\n"
        f"📈 <b>Баллы за текущий месяц:</b> <code>+{stats['month_points']}</code>\n\n"
        f"📜 <b>Последние операции:</b>\n{history_text}"
    )
    markup = profile_inline_keyboard()
    return text, markup


def render_rules_screen() -> Tuple[str, InlineKeyboardMarkup]:
    """Экран: Правила начисления баллов."""
    text = (
        "ℹ️ <b>Правила начисления баллов активности</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Баллы начисляются за участие в общественной, научной и творческой деятельности:\n\n"
        f"• 🙋 <b>Участник мероприятия:</b> <code>+{config.POINTS_PARTICIPANT}</code> баллов\n"
        f"• 🤝 <b>Помощник / Волонтер:</b> <code>+{config.POINTS_HELPER}</code> баллов\n"
        f"• 👑 <b>Организатор мероприятия:</b> <code>+{config.POINTS_ORGANIZER}</code> баллов\n\n"
        "⚖️ <b>Особые поощрения:</b>\n"
        "Кураторы и администрация могут начислять дополнительные баллы за победы в конкурсах и хакатонах, "
        "а также списывать баллы при нарушениях регламента.\n\n"
        "⚡ <b>Автоматический пересчёт:</b>\n"
        "Ваш баланс и место в турнирной таблице обновляются сразу после модерации заявки."
    )
    markup = rules_inline_keyboard()
    return text, markup


# ==========================================
# ТОЧКА ВХОДА: КОМАНДА /MENU И КНОПКА МЕНЮ
# ==========================================

@router.message(Command("menu"))
@router.message(F.text == "📱 Инлайн-меню")
async def cmd_menu(message: Message, session: AsyncSession):
    """
    Отправка одиночного интерактивного сообщения с главным меню.
    Все последующие переходы будут происходить редактированием этого сообщения.
    """
    user_id = message.from_user.id
    student = await get_student_by_telegram_id(session, user_id)

    if not student:
        await message.answer(
            "⚠️ Для доступа к меню необходимо пройти регистрацию.\n"
            "Пожалуйста, отправьте команду /start."
        )
        return

    is_admin = (user_id in config.ADMIN_IDS) or student.is_admin
    text, markup = render_main_menu_screen(student, is_admin)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


# ==========================================
# ОБРАБОТЧИКИ НАВИГАЦИИ (CALLBACK QUERY)
# ==========================================

@router.callback_query(MenuNav.filter(F.menu == "noop"))
async def callback_noop(callback: CallbackQuery):
    """Информационная кнопка (номер страницы) — гасим индикатор загрузки."""
    await callback.answer()


@router.callback_query(MenuNav.filter(F.menu == "main"))
async def callback_nav_main(callback: CallbackQuery, session: AsyncSession):
    """Переход в главное меню."""
    await callback.answer()
    student = await get_student_by_telegram_id(session, callback.from_user.id)
    if not student:
        await callback.answer("Ошибка авторизации. Отправьте /start", show_alert=True)
        return

    is_admin = (callback.from_user.id in config.ADMIN_IDS) or student.is_admin
    text, markup = render_main_menu_screen(student, is_admin)
    await safe_edit(callback, text, markup)


@router.callback_query(MenuNav.filter(F.menu == "events"))
async def callback_nav_events(callback: CallbackQuery, callback_data: MenuNav, session: AsyncSession):
    """Переход к списку мероприятий (с пагинацией)."""
    await callback.answer()
    text, markup = await render_events_list_screen(session, page=callback_data.page)
    await safe_edit(callback, text, markup)


@router.callback_query(MenuNav.filter(F.menu == "event_detail"))
async def callback_nav_event_detail(
    callback: CallbackQuery,
    callback_data: MenuNav,
    session: AsyncSession,
):
    """Переход к детальной карточке мероприятия."""
    await callback.answer()
    student = await get_student_by_telegram_id(session, callback.from_user.id)
    if not student:
        await callback.answer("Ошибка авторизации.", show_alert=True)
        return

    text, markup = await render_event_detail_screen(
        session=session,
        student=student,
        event_id=callback_data.item_id,
        page=callback_data.page,
    )
    await safe_edit(callback, text, markup)


@router.callback_query(MenuNav.filter(F.menu == "top"))
async def callback_nav_top(callback: CallbackQuery, callback_data: MenuNav, session: AsyncSession):
    """Переход к турнирной таблице лидеров (с пагинацией)."""
    await callback.answer()
    student = await get_student_by_telegram_id(session, callback.from_user.id)
    if not student:
        await callback.answer("Ошибка авторизации.", show_alert=True)
        return

    text, markup = await render_top_students_screen(
        session=session,
        current_student=student,
        page=callback_data.page,
    )
    await safe_edit(callback, text, markup)


@router.callback_query(MenuNav.filter(F.menu == "profile"))
async def callback_nav_profile(callback: CallbackQuery, session: AsyncSession):
    """Переход в профиль студента с актуализацией данных."""
    await callback.answer("Данные обновлены")
    student = await get_student_by_telegram_id(session, callback.from_user.id)
    if not student:
        await callback.answer("Ошибка авторизации.", show_alert=True)
        return

    text, markup = await render_profile_screen(session=session, student_id=student.id)
    await safe_edit(callback, text, markup)


@router.callback_query(MenuNav.filter(F.menu == "rules"))
async def callback_nav_rules(callback: CallbackQuery):
    """Переход к правилам начисления."""
    await callback.answer()
    text, markup = render_rules_screen()
    await safe_edit(callback, text, markup)


@router.callback_query(MenuNav.filter(F.menu == "admin"))
async def callback_nav_admin(callback: CallbackQuery):
    """Информационная подсказка по переходу в панель администратора."""
    await callback.answer()
    text = (
        "⚙️ <b>Панель администратора</b>\n\n"
        "Для работы с панелью куратора (модерация заявок, добавление событий, начисление баллов) "
        "используйте кнопки нижнего меню Telegram или отправьте команду /start."
    )
    markup = main_menu_inline_keyboard(is_admin=True)
    await safe_edit(callback, text, markup)


# ==========================================
# ОБРАБОТЧИКИ ДЕЙСТВИЙ (ПОДАЧА ЗАЯВКИ ВНУТРИ СООБЩЕНИЯ)
# ==========================================

@router.callback_query(EventAction.filter(F.action == "choose_role"))
async def callback_choose_role(
    callback: CallbackQuery,
    callback_data: EventAction,
    session: AsyncSession,
):
    """Экран выбора роли для участия."""
    await callback.answer()
    student = await get_student_by_telegram_id(session, callback.from_user.id)
    event = await get_event_by_id(session, callback_data.event_id)

    if not event or not event.is_active:
        await callback.answer("⚠️ Мероприятие уже завершено или недоступно.", show_alert=True)
        text, markup = await render_events_list_screen(session, page=callback_data.page)
        await safe_edit(callback, text, markup)
        return

    existing_app = await get_existing_application(session, student.id, event.id)
    if existing_app:
        await callback.answer("Вы уже подали заявку на это мероприятие!", show_alert=True)
        text, markup = await render_event_detail_screen(
            session=session,
            student=student,
            event_id=event.id,
            page=callback_data.page,
        )
        await safe_edit(callback, text, markup)
        return

    safe_title = html.escape(event.title)
    text = (
        f"🎭 <b>Выбор роли: {safe_title}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Укажите, в каком качестве вы принимали или планируете принимать участие:"
    )
    markup = event_roles_inline_keyboard(event_id=event.id, page=callback_data.page)
    await safe_edit(callback, text, markup)


@router.callback_query(EventAction.filter(F.action == "confirm"))
async def callback_confirm_role(
    callback: CallbackQuery,
    callback_data: EventAction,
    session: AsyncSession,
):
    """Экран подтверждения подачи заявки."""
    await callback.answer()
    event = await get_event_by_id(session, callback_data.event_id)
    if not event:
        await callback.answer("Мероприятие не найдено.", show_alert=True)
        return

    role = ApplicationRole(callback_data.role)
    points = config.POINTS_PARTICIPANT
    if role == ApplicationRole.HELPER:
        points = config.POINTS_HELPER
    elif role == ApplicationRole.ORGANIZER:
        points = config.POINTS_ORGANIZER

    safe_title = html.escape(event.title)
    text = (
        "📋 <b>Подтверждение заявки на участие</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎪 <b>Мероприятие:</b> {safe_title}\n"
        f"🎭 <b>Выбранная роль:</b> {role.label()}\n"
        f"⭐ <b>Баллов к начислению:</b> <code>+{points}</code>\n\n"
        "<i>Отправить заявку кураторам на модерацию?</i>"
    )
    markup = event_confirm_inline_keyboard(
        event_id=event.id,
        role=role.value,
        page=callback_data.page,
    )
    await safe_edit(callback, text, markup)


@router.callback_query(EventAction.filter(F.action == "submit"))
async def callback_submit_application(
    callback: CallbackQuery,
    callback_data: EventAction,
    session: AsyncSession,
):
    """Фиксация заявки в БД и переход к экрану успеха (всё в одном сообщении)."""
    await callback.answer("Отправка заявки...")
    student = await get_student_by_telegram_id(session, callback.from_user.id)
    event = await get_event_by_id(session, callback_data.event_id)

    if not student or not event:
        await callback.answer("Ошибка отправки заявки.", show_alert=True)
        return

    # Защита от дубликатов
    existing_app = await get_existing_application(session, student.id, event.id)
    if existing_app:
        await callback.answer("Заявка уже была отправлена ранее!", show_alert=True)
        text, markup = await render_event_detail_screen(
            session=session,
            student=student,
            event_id=event.id,
            page=callback_data.page,
        )
        await safe_edit(callback, text, markup)
        return

    role = ApplicationRole(callback_data.role)
    points = config.POINTS_PARTICIPANT
    if role == ApplicationRole.HELPER:
        points = config.POINTS_HELPER
    elif role == ApplicationRole.ORGANIZER:
        points = config.POINTS_ORGANIZER

    await create_application(
        session=session,
        student_id=student.id,
        event_id=event.id,
        role=role,
        points_calculated=points,
    )

    safe_title = html.escape(event.title)
    text = (
        "✅ <b>Заявка успешно отправлена!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎪 <b>Мероприятие:</b> {safe_title}\n"
        f"🎭 <b>Роль:</b> {role.label()} (+{points} б.)\n"
        "Статус: <b>На рассмотрении ⏳</b>\n\n"
        "<i>Куратор проверит заявку в ближайшее время. "
        "После подтверждения баллы автоматически зачислятся на ваш счёт.</i>"
    )
    markup = application_submitted_inline_keyboard(page=callback_data.page)
    await safe_edit(callback, text, markup)

    # Оповещение администраторов в фоновом режиме
    admin_notice = (
        "🔔 <b>Поступила новая заявка на модерацию!</b>\n\n"
        f"👤 Студент: <b>{html.escape(student.full_name)}</b> (гр. {html.escape(student.group_name)})\n"
        f"🎪 Мероприятие: <b>{safe_title}</b>\n"
        f"🎭 Роль: <b>{role.label()}</b> (+{points} б.)\n\n"
        "Проверить заявку можно в разделе «📥 Заявки на подтверждение» панели администратора."
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await callback.bot.send_message(
                chat_id=admin_id,
                text=admin_notice,
                parse_mode="HTML",
            )
        except Exception:
            pass
