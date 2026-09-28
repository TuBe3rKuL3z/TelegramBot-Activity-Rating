from typing import AsyncGenerator
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from bot.config import config


class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс для всех моделей SQLAlchemy."""
    pass


# Создание асинхронного движка SQLAlchemy
engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    future=True,
)

# Для SQLite включаем принудительную проверку внешних ключей
if "sqlite" in config.DATABASE_URL:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Фабрика асинхронных сессий
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Создание всех таблиц в базе данных при запуске."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор сессии для прямого использования в скриптах."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
