import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware защиты от спама и частых повторных нажатий (Anti-Flood).
    """
    def __init__(self, rate_limit: float = 0.5):
        super().__init__()
        self.rate_limit = rate_limit
        self.user_timestamps: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = time.monotonic()
            last_time = self.user_timestamps.get(user_id, 0.0)

            if now - last_time < self.rate_limit:
                # Слишком частые запросы — тихо игнорируем или уведомляем
                if isinstance(event, CallbackQuery):
                    await event.answer("Слишком часто! Подождите секунду.", show_alert=False)
                return None

            self.user_timestamps[user_id] = now

            # Периодическая очистка памяти словаря (если накопилось много записей)
            if len(self.user_timestamps) > 10000:
                self.user_timestamps = {
                    uid: ts for uid, ts in self.user_timestamps.items() if now - ts < 60
                }

        return await handler(event, data)
