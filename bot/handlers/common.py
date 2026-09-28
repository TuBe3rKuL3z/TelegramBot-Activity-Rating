from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import config
from bot.database.models import Student
from bot.database.queries import (
    create_student,
    get_student_by_telegram_id,
    update_student_admin_status,
)
from bot.keyboards.reply import (
    admin_main_keyboard,
    cancel_reply_keyboard,
    student_main_keyboard,
)
from bot.middlewares.admin import IsAdminFilter
from bot.states.states import RegistrationStates

router = Router(name="common_router")


# ==========================================
# УНИВЕРСАЛЬНЫЕ ОТМЕНЫ
# ==========================================

@router.message(Command("cancel"))
@router.message(F.text.casefold() == "❌ отмена")
async def process_cancel_text(message: Message, state: FSMContext, session: AsyncSession):
    """Сброс любого текущего состояния FSM по кнопке отмены."""
    await state.clear()
    student = await get_student_by_telegram_id(session, message.from_user.id)
    is_admin = bool((message.from_user.id in config.ADMIN_IDS) or (student and student.is_admin))

    await message.answer(
        "Действие отменено.",
        reply_markup=student_main_keyboard(is_admin=is_admin),
    )


@router.callback_query(F.data == "cancel_action")
async def process_cancel_callback(callback: CallbackQuery, state: FSMContext):
    """Сброс FSM по инлайн-кнопке отмены."""
    await state.clear()
    await callback.answer("Действие отменено.")
    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_text("❌ Действие отменено.")


# ==========================================
# КОМАНДА /START И ОНБОРДИНГ
# ==========================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """
    Точка входа. Проверяет регистрацию студента.
    Если новый — запускает FSM регистрации.
    Если уже есть — выдает главное меню.
    """
    await state.clear()
    user_id = message.from_user.id
    student = await get_student_by_telegram_id(session, user_id)

    # Если уже зарегистрирован
    if student:
        # Проверяем актуальность прав администратора
        is_admin_id = user_id in config.ADMIN_IDS
        if is_admin_id and not student.is_admin:
            student = await update_student_admin_status(session, user_id, is_admin=True)

        is_admin = is_admin_id or student.is_admin
        admin_note = "\n\n👑 *Вы авторизованы как администратор.*" if is_admin else ""

        await message.answer(
            f"👋 С возвращением, *{student.full_name}*!{admin_note}\n\n"
            "Используйте кнопки меню ниже для работы с ботом:",
            reply_markup=student_main_keyboard(is_admin=is_admin),
            parse_mode="Markdown",
        )
        return

    # Если не зарегистрирован — начинаем процесс регистрации
    await state.set_state(RegistrationStates.waiting_for_full_name)
    await message.answer(
        "👋 *Добро пожаловать в систему учёта активности и рейтинга студентов!*\n\n"
        "Для начала работы необходимо пройти быструю регистрацию.\n\n"
        "Пожалуйста, введите ваше **Фамилию, Имя и Отчество (при наличии)**:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )


@router.message(RegistrationStates.waiting_for_full_name)
async def process_registration_name(message: Message, state: FSMContext):
    """Получение и валидация ФИО."""
    full_name = message.text.strip()
    if len(full_name) < 3 or len(full_name.split()) < 2:
        await message.answer(
            "⚠️ Пожалуйста, укажите полные Фамилию и Имя (минимум 2 слова через пробел):",
            reply_markup=cancel_reply_keyboard(),
        )
        return

    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationStates.waiting_for_group)
    await message.answer(
        f"Отлично, *{full_name}*!\n\n"
        "Теперь введите вашу **учебную группу** (например: `ИС-21` или `ПИ-301`):",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="Markdown",
    )


@router.message(RegistrationStates.waiting_for_group)
async def process_registration_group(message: Message, state: FSMContext, session: AsyncSession):
    """Получение группы и сохранение студента в БД."""
    group_name = message.text.strip()
    if len(group_name) < 2 or len(group_name) > 30:
        await message.answer(
            "⚠️ Название группы должно быть от 2 до 30 символов. Попробуйте еще раз:",
            reply_markup=cancel_reply_keyboard(),
        )
        return

    data = await state.get_data()
    full_name = data.get("full_name")
    user_id = message.from_user.id
    is_admin = user_id in config.ADMIN_IDS

    student = await create_student(
        session=session,
        telegram_id=user_id,
        full_name=full_name,
        group_name=group_name,
        is_admin=is_admin,
    )

    await state.clear()

    admin_note = "\n\n👑 *Вам автоматически выданы права администратора.*" if is_admin else ""
    await message.answer(
        f"🎉 *Регистрация успешно завершена!*\n\n"
        f"👤 Студент: {student.full_name}\n"
        f"👥 Группа: {student.group_name}\n"
        f"⭐ Начальный баланс: {student.total_points} баллов{admin_note}\n\n"
        "Выберите действие в меню ниже:",
        reply_markup=student_main_keyboard(is_admin=is_admin),
        parse_mode="Markdown",
    )


# ==========================================
# ПЕРЕКЛЮЧЕНИЕ РОЛЕЙ И РАЗДЕЛОВ
# ==========================================

@router.message(F.text == "⚙️ Панель администратора", IsAdminFilter())
async def open_admin_panel(message: Message, state: FSMContext):
    """Переход в панель администратора."""
    await state.clear()
    await message.answer(
        "⚙️ *Панель администратора открыта.*\n"
        "Выберите необходимый инструмент управления:",
        reply_markup=admin_main_keyboard(),
        parse_mode="Markdown",
    )


@router.message(F.text == "🔙 Главное меню студента")
async def back_to_student_menu(message: Message, state: FSMContext, session: AsyncSession):
    """Возврат в меню студента."""
    await state.clear()
    user_id = message.from_user.id
    student = await get_student_by_telegram_id(session, user_id)
    is_admin = bool((user_id in config.ADMIN_IDS) or (student and student.is_admin))

    await message.answer(
        "Вы вернулись в главное меню студента:",
        reply_markup=student_main_keyboard(is_admin=is_admin),
    )
