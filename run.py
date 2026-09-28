"""
Запуск Telegram-бота учёта активности студентов.
Запуск: python run.py
"""
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from bot.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
