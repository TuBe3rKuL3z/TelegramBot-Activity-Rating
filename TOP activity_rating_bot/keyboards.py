from telebot import types

#Клавиатура для студента
def student_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = types.KeyboardButton("Отметить участие")
    btn2 = types.KeyboardButton("Мой рейтинг")
    btn3 = types.KeyboardButton("Топ студентов")
    btn4 = types.KeyboardButton("Правила начисления баллов")

    markup.add(btn1, btn2, btn3, btn4)
    return markup


#Клавиатура для админа
def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = types.KeyboardButton("Панель администратора")
    btn2 = types.KeyboardButton("Добавить мероприятие")
    btn3 = types.KeyboardButton("Рейтинг и статистика")

    markup.add(btn1, btn2, btn3)
    return markup


#Инлайн-кнопки для подтверждения заявок (появятся позже)
def request_buttons(request_id):
    markup = types.InlineKeyboardMarkup(row_width=2)

    confirm = types.InlineKeyboardButton("Подтвердить", callback_data=f"confirm_{request_id}")
    reject = types.InlineKeyboardButton("Отклонить", callback_data=f"reject_{request_id}")
    edit = types.InlineKeyboardButton("Изменить", callback_data=f"edit_{request_id}")

    markup.add(confirm, reject, edit)
    return markup