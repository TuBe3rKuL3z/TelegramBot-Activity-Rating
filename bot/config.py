import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Конфигурация проекта с загрузкой из переменных окружения или .env файла.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    BOT_TOKEN: str = "8449168724:AAHVmO7TabMJtTSjCGk9bg6hdCrNhRMEmjU"
    ADMIN_IDS: Union[List[int], str] = [6504935113]
    DATABASE_URL: str = "sqlite+aiosqlite:///activity_rating.db"

    # Конфигурация базовых баллов за роли
    POINTS_PARTICIPANT: int = 5
    POINTS_HELPER: int = 10
    POINTS_ORGANIZER: int = 20

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Union[str, int, List[int]]) -> List[int]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        elif isinstance(v, int):
            return [v]
        elif isinstance(v, list):
            return [int(x) for x in v]
        return []


config = Settings()
