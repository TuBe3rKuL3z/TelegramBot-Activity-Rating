import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path для корректных абсолютных импортов
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import config
from bot.database.base import engine, init_db
from bot.handlers import admin_router, common_router, student_router
from bot.middlewares import DbSessionMiddleware, ThrottlingMiddleware, UserContextMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s : %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("activity_rating_bot")


async def on_startup(bot: Bot) -> None:
    """Действия при старте бота."""
    logger.info("Инициализация базы данных...")
    await init_db()

    bot_info = await bot.get_me()
    logger.info("Бот успешно запущен: @%s [ID: %s]", bot_info.username, bot_info.id)
    logger.info("Зарегистрированные администраторы: %s", config.ADMIN_IDS)


async def on_shutdown(bot: Bot) -> None:
    """Действия при завершении работы бота."""
    logger.info("Остановка бота и закрытие соединений...")
    await bot.session.close()
    await engine.dispose()
    logger.info("Все соединения закрыты. Бот остановлен.")


async def main() -> None:
    """Главная функция инициализации и запуска бота."""
    logger.info("Запуск приложения Activity Rating Bot...")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # 1. Регистрация базового Middleware сессии БД на весь жизненный цикл Update
    dp.update.middleware(DbSessionMiddleware())

    # 2. Регистрация Throttling Middleware (Anti-Flood)
    throttling = ThrottlingMiddleware(rate_limit=0.5)
    dp.message.middleware(throttling)
    dp.callback_query.middleware(throttling)

    # 3. Регистрация Middleware обогащения контекста пользователем
    user_context = UserContextMiddleware()
    dp.message.middleware(user_context)
    dp.callback_query.middleware(user_context)

    # 4. Регистрация роутеров
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(student_router)

    # Регистрация хуков запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Сброс накопившихся апдейтов и запуск Polling
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
