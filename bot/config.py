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

    BOT_TOKEN: str = ""
    ADMIN_IDS: Union[List[int], str] = []
    DATABASE_URL: str = "sqlite+aiosqlite:///activity_rating.db"
    DB_URL: Union[str, None] = None

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

    def model_post_init(self, __context) -> None:
        if self.DB_URL and (not self.DATABASE_URL or self.DATABASE_URL == "sqlite+aiosqlite:///activity_rating.db"):
            self.DATABASE_URL = self.DB_URL


config = Settings()
