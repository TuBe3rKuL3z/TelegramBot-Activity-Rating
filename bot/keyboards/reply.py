from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def student_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главная клавиатура студента."""
    keyboard = [
        [
            KeyboardButton(text="📱 Инлайн-меню"),
        ],
        [
            KeyboardButton(text="🎯 Отметить участие"),
            KeyboardButton(text="📊 Мой рейтинг"),
        ],
        [
            KeyboardButton(text="🏆 Топ студентов"),
            KeyboardButton(text="📋 Правила начисления"),
        ],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Панель администратора")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура панели администратора."""
    keyboard = [
        [
            KeyboardButton(text="📥 Заявки на подтверждение"),
            KeyboardButton(text="➕ Добавить мероприятие"),
        ],
        [
            KeyboardButton(text="⚖️ Ручные баллы"),
            KeyboardButton(text="📈 Рейтинг и статистика"),
        ],
        [
            KeyboardButton(text="🔙 Главное меню студента"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены действия."""
    keyboard = [
        [KeyboardButton(text="❌ Отмена")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True,
    )
