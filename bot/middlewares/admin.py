from typing import Any, Awaitable, Callable, Dict, Union
from aiogram import BaseMiddleware
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import config
from bot.database.queries import get_student_by_telegram_id


class IsAdminFilter(Filter):
    """
    Фильтр проверки прав администратора.
    Проверяет вхождение ID в config.ADMIN_IDS или флаг is_admin в базе данных.
    """
    async def __call__(self, event: Union[Message, CallbackQuery], session: AsyncSession) -> bool:
        if not event.from_user:
            return False

        user_id = event.from_user.id
        if user_id in config.ADMIN_IDS:
            return True

        student = await get_student_by_telegram_id(session, user_id)
        return bool(student and student.is_admin)


class UserContextMiddleware(BaseMiddleware):
    """
    Middleware для прикрепления объекта студента и статуса админа к контексту хендлера.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data.get("session")
        user_id = None

        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id

        if session and user_id:
            student = await get_student_by_telegram_id(session, user_id)
            is_admin = (user_id in config.ADMIN_IDS) or bool(student and student.is_admin)

            # Если пользователь в ADMIN_IDS, но в БД флаг не проставлен — синхронизируем
            if user_id in config.ADMIN_IDS and student and not student.is_admin:
                student.is_admin = True
                await session.commit()
                await session.refresh(student)

            data["student"] = student
            data["is_admin"] = is_admin

        return await handler(event, data)
