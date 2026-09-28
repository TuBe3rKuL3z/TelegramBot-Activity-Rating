from datetime import datetime
from typing import Any, Optional, Tuple
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import config
from bot.database.models import ApplicationRole, EventType, Student
from bot.database.queries import (
    add_points_to_student,
    approve_application,
    count_pending_applications,
    create_event,
    get_application_by_id,
    get_general_statistics,
    get_pending_applications,
    get_student_by_id,
    get_top_students,
    reject_application,
    search_students,
)
from bot.keyboards.inline import (
    application_review_keyboard,
    cancel_inline_keyboard,
    event_type_inline_keyboard,
    student_selection_keyboard,
)
from bot.keyboards.reply import admin_main_keyboard, cancel_reply_keyboard
from bot.middlewares.admin import IsAdminFilter
from bot.states.states import (
    AdminEventStates,
    AdminManualPointsStates,
    AdminReviewStates,
)

router = Router(name="admin_router")
# Применяем фильтр администратора ко всем хендлерам данного роутера
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


# ==========================================
# МОДЕРАЦИЯ ЗАЯВОК (REVIEW APPLICATIONS)
# ==========================================

async def render_application_card(session: AsyncSession, page: int = 0) -> Tuple[str, Any]:
    """Вспомогательная функция формирования текста и клавиатуры карточки заявки."""
    total_pending = await count_pending_applications(session)
    if total_pending == 0:
        return (
            "🎉 *Все заявки проверены!*\nВ очереди модерации нет заявок, ожидающих подтверждения.",
            None,
        )

    # Коррекция индекса страницы
    page = max(0, min(page, total_pending - 1))
    apps = await get_pending_applications(session, offset=page, limit=1)
    if not apps:
        return "В очереди нет заявок.", None

    app = apps[0]
    student = app.student
    event = app.event

    text = (
        f"📥 *Заявка на модерации* (№{app.id})\n"
        f"Заявка *{page + 1}* из *{total_pending}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Студент:* {student.full_name}\n"
        f"👥 *Группа:* `{student.group_name}` (ID: `{student.telegram_id}`)\n"
        f"🎪 *Мероприятие:* {event.title}\n"
        f"📅 *Дата:* {event.event_date.strftime('%d.%m.%Y')}\n"
        f"🎭 *Заявленная роль:* {app.role.label()}\n"
        f"⭐ *Баллов к начислению:* `+{app.points_calculated}`\n"
        f"🕒 *Подана:* {app.created_at.strftime('%d.%m.%Y %H:%M')}"
    )

    markup = application_review_keyboard(app_id=app.id, current_page=page, total_pages=total_pending)
    return text, markup


@router.message(F.text == "📥 Заявки на подтверждение")
async def show_pending_applications(message: Message, session: AsyncSession):
    """Открыть список заявок на подтверждение."""
    text, markup = await render_application_card(session, page=0)
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")


@router.callback_query(F.data.startswith("rev_page:"))
async def process_review_pagination(callback: CallbackQuery, session: AsyncSession):
    """Переключение между карточками заявок."""
    page = int(callback.data.split(":")[1])
    text, markup = await render_application_card(session, page=page)
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("rev_approve:"))
async def process_approve_application(callback: CallbackQuery, session: AsyncSession):
    """Одобрение заявки администратором."""
    parts = callback.data.split(":")
    app_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    approved_app = await approve_application(session, app_id=app_id)
    if not approved_app:
        await callback.answer("⚠️ Заявка уже обработана или не найдена.", show_alert=True)
    else:
        await callback.answer("✅ Заявка одобрена, баллы начислены!")

        # Оповещение студента
        try:
            student = approved_app.student
            event_title = approved_app.event.title if approved_app.event else "Мероприятие"
            user_msg = (
                f"🎉 *Ваша заявка одобрена!*\n\n"
                f"🎪 Мероприятие: *{event_title}*\n"
                f"🎭 Роль: *{approved_app.role.label()}*\n"
                f"⭐ Начислено: *+{approved_app.points_calculated} баллов*\n\n"
                f"Ваш текущий баланс: `{student.total_points}` б."
            )
            await callback.bot.send_message(
                chat_id=student.telegram_id,
                text=user_msg,
                parse_mode="Markdown",
            )
        except Exception:
            pass

    # Обновление экрана модерации
    text, markup = await render_application_card(session, page=page)
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=markup, parse_mode="Markdown")


@router.callback_query(F.data.startswith("rev_reject:"))
async def process_reject_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос причины отклонения заявки."""
    parts = callback.data.split(":")
    app_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    await state.set_state(AdminReviewStates.waiting_for_reject_reason)
    await state.update_data(app_id=app_id, page=page)

    await callback.message.answer(
        f"❌ *Отклонение заявки №{app_id}*\n\n"
        "Введите причину отклонения (она будет отправлена студенту), "
        "или отправьте `-` если хотите отклонить без подробного описания:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminReviewStates.waiting_for_reject_reason)
async def process_reject_reason_input(message: Message, state: FSMContext, session: AsyncSession):
    """Завершение отклонения заявки с отправкой уведомления."""
    reason = message.text.strip()
    if reason == "-":
        reason = "Не соответствует требованиям регламента."

    data = await state.get_data()
    app_id = data.get("app_id")
    page = data.get("page", 0)

    rejected_app = await reject_application(session, app_id=app_id, reason=reason)
    await state.clear()

    if rejected_app:
        await message.answer("❌ Заявка отклонена.", reply_markup=admin_main_keyboard())

        # Уведомляем студента
        try:
            student = rejected_app.student
            event_title = rejected_app.event.title if rejected_app.event else "Мероприятие"
            user_msg = (
                f"❌ *Ваша заявка отклонена куратором*\n\n"
                f"🎪 Мероприятие: *{event_title}*\n"
                f"💬 Причина: {reason}\n\n"
                "Если у вас есть вопросы, обратитесь к организаторам."
            )
            await message.bot.send_message(
                chat_id=student.telegram_id,
                text=user_msg,
                parse_mode="Markdown",
            )
        except Exception:
            pass
    else:
        await message.answer("Заявка уже была обработана ранее.", reply_markup=admin_main_keyboard())

    # Показываем следующую заявку
    text, markup = await render_application_card(session, page=page)
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")


@router.callback_query(F.data.startswith("rev_edit:"))
async def process_edit_points_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос нового количества баллов для одобрения заявки."""
    parts = callback.data.split(":")
    app_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    await state.set_state(AdminReviewStates.waiting_for_custom_points)
    await state.update_data(app_id=app_id, page=page)

    await callback.message.answer(
        f"✏️ *Изменение баллов для заявки №{app_id}*\n\n"
        "Введите точное количество баллов, которое нужно начислить студенту (целое положительное число):",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminReviewStates.waiting_for_custom_points)
async def process_custom_points_input(message: Message, state: FSMContext, session: AsyncSession):
    """Применение кастомных баллов и одобрение заявки."""
    points_text = message.text.strip()
    if not points_text.isdigit() or int(points_text) < 0:
        await message.answer("⚠️ Пожалуйста, введите положительное целое число баллов (например: `15`):")
        return

    custom_points = int(points_text)
    data = await state.get_data()
    app_id = data.get("app_id")
    page = data.get("page", 0)

    approved_app = await approve_application(session, app_id=app_id, custom_points=custom_points)
    await state.clear()

    if approved_app:
        await message.answer(
            f"✅ Заявка №{app_id} одобрена с начислением {custom_points} баллов!",
            reply_markup=admin_main_keyboard(),
        )

        try:
            student = approved_app.student
            event_title = approved_app.event.title if approved_app.event else "Мероприятие"
            user_msg = (
                f"🎉 *Ваша заявка одобрена!*\n\n"
                f"🎪 Мероприятие: *{event_title}*\n"
                f"🎭 Роль: *{approved_app.role.label()}*\n"
                f"⭐ Начислено: *+{custom_points} баллов* (скорректировано куратором)\n\n"
                f"Ваш текущий баланс: `{student.total_points}` б."
            )
            await message.bot.send_message(
                chat_id=student.telegram_id,
                text=user_msg,
                parse_mode="Markdown",
            )
        except Exception:
            pass
    else:
        await message.answer("⚠️ Заявка уже была обработана.", reply_markup=admin_main_keyboard())

    text, markup = await render_application_card(session, page=page)
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")


@router.callback_query(F.data == "admin_menu_back")
async def process_admin_menu_back(callback: CallbackQuery):
    """Закрытие просмотра модерации."""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Панель администратора:", reply_markup=admin_main_keyboard())
    await callback.answer()


# ==========================================
# СОЗДАНИЕ МЕРОПРИЯТИЯ (ADD EVENT FSM)
# ==========================================

@router.message(F.text == "➕ Добавить мероприятие")
async def start_add_event(message: Message, state: FSMContext):
    """Начало сценария добавления мероприятия."""
    await state.set_state(AdminEventStates.waiting_for_title)
    await message.answer(
        "🎪 *Добавление нового мероприятия*\n\n"
        "Шаг 1 из 3: Введите **название мероприятия**:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )


@router.message(AdminEventStates.waiting_for_title)
async def process_event_title(message: Message, state: FSMContext):
    """Сохранение названия и запрос даты."""
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("⚠️ Название слишком короткое. Введите понятное название события:")
        return

    await state.update_data(title=title)
    await state.set_state(AdminEventStates.waiting_for_date)
    await message.answer(
        f"Название: *{title}*\n\n"
        "Шаг 2 из 3: Введите **дату проведения** в формате `ДД.ММ.ГГГГ` (например: `15.11.2026`) "
        "или напишите `сегодня`:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )


@router.message(AdminEventStates.waiting_for_date)
async def process_event_date(message: Message, state: FSMContext):
    """Парсинг даты проведения."""
    date_text = message.text.strip().lower()

    if date_text in ("сегодня", "today"):
        event_date = datetime.now()
    else:
        parsed = None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
            try:
                parsed = datetime.strptime(date_text, fmt)
                break
            except ValueError:
                continue

        if not parsed:
            await message.answer(
                "⚠️ Не удалось распознать формат даты.\n"
                "Пожалуйста, введите дату в виде `ДД.ММ.ГГГГ` (например: `25.10.2026`):"
            )
            return
        event_date = parsed

    await state.update_data(event_date=event_date.isoformat())
    await state.set_state(AdminEventStates.waiting_for_type)

    await message.answer(
        "Шаг 3 из 3: Выберите **направление/тип мероприятия**:",
        reply_markup=event_type_inline_keyboard(),
        parse_mode="Markdown",
    )


@router.callback_query(AdminEventStates.waiting_for_type, F.data.startswith("event_type:"))
async def process_event_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Фиксация мероприятия в БД."""
    type_str = callback.data.split(":")[1]
    event_type = EventType(type_str)

    data = await state.get_data()
    title = data.get("title")
    event_date = datetime.fromisoformat(data.get("event_date"))

    event = await create_event(
        session=session,
        title=title,
        event_date=event_date,
        event_type=event_type,
        is_active=True,
    )

    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        f"✅ *Мероприятие успешно создано!*\n\n"
        f"🎪 *Название:* {event.title}\n"
        f"📅 *Дата:* {event.event_date.strftime('%d.%m.%Y')}\n"
        f"📂 *Тип:* {event.event_type.label()}\n"
        f"🟢 *Статус:* Активно (доступно студентам для записи)",
        reply_markup=admin_main_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ==========================================
# РУЧНОЕ НАЧИСЛЕНИЕ / СПИСАНИЕ БАЛЛОВ (FSM)
# ==========================================

@router.message(F.text == "⚖️ Ручные баллы")
async def start_manual_points(message: Message, state: FSMContext):
    """Старт ручного начисления/списания баллов."""
    await state.set_state(AdminManualPointsStates.waiting_for_student_query)
    await message.answer(
        "⚖️ *Ручное начисление / списание баллов*\n\n"
        "Шаг 1 из 3: Введите Telegram ID, фамилию или группу студента для поиска:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )


@router.message(AdminManualPointsStates.waiting_for_student_query)
async def process_student_search(message: Message, state: FSMContext, session: AsyncSession):
    """Поиск студента по введенному запросу."""
    query_text = message.text.strip()
    found_students = await search_students(session, query_text)

    if not found_students:
        await message.answer(
            f"🔍 По запросу «{query_text}» никого не найдено.\n"
            "Попробуйте ввести точный Telegram ID или часть фамилии:"
        )
        return

    if len(found_students) == 1:
        student = found_students[0]
        await state.update_data(student_id=student.id, student_name=student.full_name)
        await state.set_state(AdminManualPointsStates.waiting_for_amount)
        await message.answer(
            f"👤 Найден студент: *{student.full_name}* (гр. {student.group_name})\n"
            f"Текущий баланс: `{student.total_points}` б.\n\n"
            "Шаг 2 из 3: Введите количество баллов для начисления (например: `+15`) "
            "или списания (например: `-10`):",
            reply_markup=cancel_reply_keyboard(),
            parse_mode="Markdown",
        )
    else:
        # Несколько совпадений — даем выбор через инлайн-клавиатуру
        await state.set_state(AdminManualPointsStates.selecting_student)
        await message.answer(
            f"Найдено {len(found_students)} студентов. Выберите нужного:",
            reply_markup=student_selection_keyboard(found_students),
        )


@router.callback_query(
    AdminManualPointsStates.selecting_student,
    F.data.startswith("select_student:"),
)
async def process_student_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор студента из списка нескольких результатов."""
    student_id = int(callback.data.split(":")[1])
    student = await get_student_by_id(session, student_id)

    if not student:
        await callback.answer("Студент не найден.", show_alert=True)
        return

    await state.update_data(student_id=student.id, student_name=student.full_name)
    await state.set_state(AdminManualPointsStates.waiting_for_amount)

    await callback.message.delete()
    await callback.message.answer(
        f"👤 Выбран: *{student.full_name}* (гр. {student.group_name})\n"
        f"Текущий баланс: `{student.total_points}` б.\n\n"
        "Шаг 2 из 3: Введите количество баллов (например: `+20` или `-5`):",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminManualPointsStates.waiting_for_amount)
async def process_points_amount(message: Message, state: FSMContext):
    """Валидация суммы баллов."""
    amount_str = message.text.strip().replace("+", "")
    try:
        amount = int(amount_str)
        if amount == 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите ненулевое целое число, например: `+10` или `-5`:")
        return

    await state.update_data(amount=amount)
    await state.set_state(AdminManualPointsStates.waiting_for_reason)

    action_word = "начисления" if amount > 0 else "списания"
    await message.answer(
        f"Шаг 3 из 3: Укажите **причину** {action_word} баллов:\n"
        f"(например: «Победа в региональном хакатоне» или «Дежурство»)",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )


@router.message(AdminManualPointsStates.waiting_for_reason)
async def process_points_reason(message: Message, state: FSMContext, session: AsyncSession):
    """Применение баллов и уведомление студента."""
    reason = message.text.strip()
    data = await state.get_data()
    student_id = data.get("student_id")
    amount = data.get("amount")

    updated_student = await add_points_to_student(
        session=session,
        student_id=student_id,
        amount=amount,
        reason=reason,
    )

    await state.clear()

    if not updated_student:
        await message.answer("Ошибка: студент не найден в базе данных.", reply_markup=admin_main_keyboard())
        return

    sign = "+" if amount > 0 else ""
    await message.answer(
        f"✅ *Баллы успешно обновлены!*\n\n"
        f"👤 Студент: *{updated_student.full_name}*\n"
        f"Изменение: *{sign}{amount} баллов*\n"
        f"Причина: _{reason}_\n"
        f"Итоговый баланс: `{updated_student.total_points}` б.",
        reply_markup=admin_main_keyboard(),
        parse_mode="Markdown",
    )

    # Уведомляем студента
    try:
        student_notice = (
            f"ℹ️ *Уведомление об изменении рейтинга*\n\n"
            f"Вам {'начислено' if amount > 0 else 'списано'} *{sign}{amount} баллов*.\n"
            f"💬 Причина: _{reason}_\n"
            f"⭐ Ваш новый баланс: `{updated_student.total_points}` б."
        )
        await message.bot.send_message(
            chat_id=updated_student.telegram_id,
            text=student_notice,
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ==========================================
# СТАТИСТИКА И СВОДНЫЙ РЕЙТИНГ
# ==========================================

@router.message(F.text == "📈 Рейтинг и статистика")
async def show_admin_statistics(message: Message, session: AsyncSession):
    """Сводный аналитический отчет для куратора."""
    stats = await get_general_statistics(session)
    top_5 = await get_top_students(session, limit=5)

    leaders_text = ""
    if top_5:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        leaders_lines = []
        for idx, s in enumerate(top_5, 1):
            badge = medals.get(idx, f"{idx}.")
            leaders_lines.append(f"{badge} *{s.full_name}* ({s.group_name}) — `{s.total_points}` б.")
        leaders_text = "\n\n🏆 *Топ-5 лидеров:*\n" + "\n".join(leaders_lines)

    report = (
        "📈 *Сводная статистика системы активности*\n\n"
        f"👥 Всего зарегистрировано студентов: `{stats['total_students']}`\n"
        f"🎪 Всего мероприятий: `{stats['total_events']}` (активных сейчас: `{stats['active_events']}`)\n\n"
        f"📋 *Статистика заявок:*\n"
        f"• ⏳ Ожидают проверки: `{stats['pending_apps']}`\n"
        f"• ✅ Одобрено: `{stats['approved_apps']}`\n"
        f"• ❌ Отклонено: `{stats['rejected_apps']}`\n\n"
        f"⭐ Всего начислено баллов студентам: `{stats['total_points']}`"
        f"{leaders_text}"
    )

    await message.answer(report, parse_mode="Markdown")
