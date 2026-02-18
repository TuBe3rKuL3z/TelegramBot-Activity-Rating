import telebot
import config
import keyboards

bot = telebot.TeleBot(config.BOT_TOKEN)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    if user_id == config.ADMIN_ID:
        bot.reply_to(
            message,
            f'Привет, {user_name}! Режим администратора активирован!',
            reply_markup=keyboards.admin_keyboard()
        )
    else:
        bot.reply_to(
            message,
            f'Привет, {user_name}! Режим участника активирован!',
            reply_markup = keyboards.student_keyboard()
        )


#Обработчик нажатий на кнопки
@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    user_id = message.from_user.id
    text = message.text

    #Админ
    if user_id == config.ADMIN_ID:
        if text == "Панель администратора":
            bot.send_message(message.chat.id, "Раздел в разработке")

        elif text == "Добавить мероприятие":
            bot.send_message(message.chat.id, "Раздел в разработке")

        elif text == "Рейтинг и статистика":
            bot.send_message(message.chat.id, "Раздел в разработке")
    #Студенты
    else:
        if text == "Отметить участие":
            bot.send_message(message.chat.id, "Раздел в разработке")

        elif text == "Мой рейтинг":
            bot.send_message(message.chat.id, "Раздел в разработке")

        elif text == "Топ студентов":
            bot.send_message(message.chat.id, "Раздел в разработке")

        elif text == "Правила начисления баллов":
            rules = """
📋 *Правила начисления баллов:*

• Участник мероприятия: +5 баллов
• Помощник в организации: +10 баллов
• Организатор мероприятия: +15 баллов

*Как часто обновляется рейтинг:*
Рейтинг обновляется сразу после подтверждения заявки администратором.
            """
            bot.send_message(message.chat.id, rules, parse_mode='Markdown')


# Запуск бота
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()