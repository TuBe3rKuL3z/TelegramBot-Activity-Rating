from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from bot.database.base import async_session


class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware внедрения сессии SQLAlchemy в контекст каждого апдейта.
    Сессия автоматически закрывается и откатывается при ошибке.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)
