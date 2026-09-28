from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import config
from bot.database.models import ApplicationRole, Student
from bot.database.queries import (
    create_application,
    get_active_events,
    get_event_by_id,
    get_existing_application,
    get_student_by_telegram_id,
    get_student_rank_and_stats,
    get_top_students,
)
from bot.keyboards.inline import (
    confirm_application_keyboard,
    events_inline_keyboard,
    roles_inline_keyboard,
)
from bot.keyboards.reply import student_main_keyboard
from bot.states.states import StudentApplicationStates

router = Router(name="student_router")


# ==========================================
# ПОДАЧА ЗАЯВКИ НА УЧАСТИЕ (FSM)
# ==========================================

@router.message(F.text == "🎯 Отметить участие")
async def start_application_flow(message: Message, state: FSMContext, session: AsyncSession):
    """Начало сценария подачи заявки на участие."""
    student = await get_student_by_telegram_id(session, message.from_user.id)
    if not student:
        await message.answer("⚠️ Вы не зарегистрированы. Пожалуйста, отправьте команду /start.")
        return

    active_events = await get_active_events(session)
    if not active_events:
        await message.answer(
            "📍 В данный момент нет открытых мероприятий для регистрации.\n"
            "Следите за обновлениями или обратитесь к куратору."
        )
        return

    await state.set_state(StudentApplicationStates.selecting_event)
    await message.answer(
        "🎪 *Выберите мероприятие*, в котором вы принимали или принимаете участие:",
        reply_markup=events_inline_keyboard(active_events),
        parse_mode="Markdown",
    )


@router.callback_query(
    StudentApplicationStates.selecting_event,
    F.data.startswith("event:"),
)
async def process_event_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора мероприятия."""
    event_id = int(callback.data.split(":")[1])
    event = await get_event_by_id(session, event_id)

    if not event or not event.is_active:
        await callback.answer("⚠️ Это мероприятие больше не активно.", show_alert=True)
        await callback.message.delete()
        await state.clear()
        return

    student = await get_student_by_telegram_id(session, callback.from_user.id)
    # Проверка на наличие уже существующей заявки
    existing_app = await get_existing_application(session, student.id, event.id)
    if existing_app:
        status_label = existing_app.status.label()
        await callback.answer(
            f"Вы уже подавали заявку на это событие!\nСтатус: {status_label}",
            show_alert=True,
        )
        return

    await state.update_data(event_id=event.id, event_title=event.title)
    await state.set_state(StudentApplicationStates.selecting_role)

    await callback.message.edit_text(
        f"Вы выбрали: *{event.title}*\n"
        f"📅 Дата проведения: {event.event_date.strftime('%d.%m.%Y')}\n\n"
        "Теперь укажите вашу роль на данном мероприятии:",
        reply_markup=roles_inline_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(
    StudentApplicationStates.selecting_role,
    F.data.startswith("role:"),
)
async def process_role_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора роли студента."""
    role_str = callback.data.split(":")[1]
    role = ApplicationRole(role_str)

    # Расчет баллов в соответствии с конфигурацией
    points = config.POINTS_PARTICIPANT
    if role == ApplicationRole.HELPER:
        points = config.POINTS_HELPER
    elif role == ApplicationRole.ORGANIZER:
        points = config.POINTS_ORGANIZER

    await state.update_data(role=role.value, points=points)
    data = await state.get_data()
    event_title = data.get("event_title")

    await state.set_state(StudentApplicationStates.confirming)
    await callback.message.edit_text(
        "📋 *Проверьте данные вашей заявки:*\n\n"
        f"🎪 *Мероприятие:* {event_title}\n"
        f"🎭 *Роль:* {role.label()}\n"
        f"⭐ *Баллов к начислению:* +{points}\n\n"
        "Отправить заявку кураторам на подтверждение?",
        reply_markup=confirm_application_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(
    StudentApplicationStates.confirming,
    F.data == "app:confirm",
)
async def process_application_submission(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Фиксация заявки в БД и уведомление администраторов."""
    data = await state.get_data()
    event_id = data.get("event_id")
    role_str = data.get("role")
    points = data.get("points")

    student = await get_student_by_telegram_id(session, callback.from_user.id)
    if not student:
        await callback.answer("Ошибка авторизации.", show_alert=True)
        await state.clear()
        return

    # Создание заявки в статусе PENDING
    application = await create_application(
        session=session,
        student_id=student.id,
        event_id=event_id,
        role=ApplicationRole(role_str),
        points_calculated=points,
    )

    await state.clear()
    await callback.message.edit_text(
        "✅ *Заявка успешно отправлена на проверку!*\n\n"
        "После того как куратор проверит и подтвердит участие, баллы сразу зачислятся в ваш рейтинг.",
        parse_mode="Markdown",
    )
    await callback.answer()

    # Оповещение администраторов
    event = await get_event_by_id(session, event_id)
    event_title = event.title if event else "Мероприятие"
    role_name = ApplicationRole(role_str).label()

    admin_notice = (
        "🔔 *Поступила новая заявка на модерацию!*\n\n"
        f"👤 Студент: *{student.full_name}* (гр. {student.group_name})\n"
        f"🎪 Мероприятие: *{event_title}*\n"
        f"🎭 Роль: *{role_name}* (+{points} б.)\n\n"
        "Просмотреть заявку можно в разделе «📥 Заявки на подтверждение» панели администратора."
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await callback.bot.send_message(chat_id=admin_id, text=admin_notice, parse_mode="Markdown")
        except Exception:
            pass  # Если бот заблокирован админом или не начат диалог


# ==========================================
# МОЙ РЕЙТИНГ И СТАТИСТИКА
# ==========================================

@router.message(F.text == "📊 Мой рейтинг")
async def show_my_rating(message: Message, session: AsyncSession):
    """Отображение личного профиля, текущего рейтинга и недавней истории."""
    student = await get_student_by_telegram_id(session, message.from_user.id)
    if not student:
        await message.answer("⚠️ Вы не зарегистрированы. Отправьте /start для регистрации.")
        return

    stats = await get_student_rank_and_stats(session, student.id)

    # Формируем блок последних начислений
    history_lines = []
    if student.points_history:
        for item in student.points_history[:4]:
            sign = "+" if item.amount > 0 else ""
            date_str = item.created_at.strftime("%d.%m")
            history_lines.append(f"• `{date_str}`: *{sign}{item.amount} б.* — {item.reason}")
    else:
        history_lines.append("• Начислений пока не было.")

    history_text = "\n".join(history_lines)

    text = (
        f"📊 *Ваш личный рейтинг активности*\n\n"
        f"👤 *Студент:* {student.full_name}\n"
        f"👥 *Группа:* {student.group_name}\n\n"
        f"⭐ *Всего баллов:* `{student.total_points}`\n"
        f"🏅 *Место в общем рейтинге:* `#{stats['rank']}` из `{stats['total_students']}`\n"
        f"📈 *Баллы за текущий месяц:* `{stats['month_points']}`\n\n"
        f"📜 *Последние операции:*\n{history_text}"
    )

    await message.answer(text, parse_mode="Markdown")


# ==========================================
# ТОП СТУДЕНТОВ
# ==========================================

@router.message(F.text == "🏆 Топ студентов")
async def show_top_students(message: Message, session: AsyncSession):
    """Вывод турнирной таблицы лидеров."""
    top_list = await get_top_students(session, limit=10)
    current_student = await get_student_by_telegram_id(session, message.from_user.id)

    if not top_list:
        await message.answer("🏆 Рейтинговая таблица пока пуста. Будьте первыми!")
        return

    lines = ["🏆 *Топ-10 студентов по активности:*\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for index, student in enumerate(top_list, start=1):
        badge = medals.get(index, f"{index}.")
        is_me = " *(Вы)*" if current_student and current_student.id == student.id else ""
        lines.append(
            f"{badge} *{student.full_name}* ({student.group_name}) — `{student.total_points}` б.{is_me}"
        )

    # Если текущий пользователь не входит в топ-10, показываем его позицию внизу
    if current_student and not any(s.id == current_student.id for s in top_list):
        stats = await get_student_rank_and_stats(session, current_student.id)
        lines.append(f"\n───────────────\nВаша позиция: `#{stats['rank']}` — `{current_student.total_points}` б.")

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ==========================================
# ПРАВИЛА НАЧИСЛЕНИЯ
# ==========================================

@router.message(F.text == "📋 Правила начисления")
async def show_rules(message: Message):
    """Справочная информация о системе баллов."""
    text = (
        "📋 *Регламент начисления баллов активности*\n\n"
        "Баллы начисляются за участие в общественной, научной и творческой жизни:\n\n"
        f"• 🙋 *Участник мероприятия:* `+{config.POINTS_PARTICIPANT}` баллов\n"
        f"• 🤝 *Помощник / Волонтер:* `+{config.POINTS_HELPER}` баллов\n"
        f"• 👑 *Организатор мероприятия:* `+{config.POINTS_ORGANIZER}` баллов\n\n"
        "⚖️ *Особые поощрения и штрафы:*\n"
        "Администрация вправе поощрять студентов дополнительными баллами за победы в конкурсах и хакатонах, "
        "а также списывать баллы за нарушение дисциплины.\n\n"
        "⚡ *Обновление рейтинга:*\n"
        "Рейтинг пересчитывается моментально после подтверждения вашей заявки куратором."
    )
    await message.answer(text, parse_mode="Markdown")
