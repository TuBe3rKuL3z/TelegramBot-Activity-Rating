from typing import Optional
from aiogram.filters.callback_data import CallbackData


class MenuNav(CallbackData, prefix="nav"):
    """
    Типизированная фабрика для навигации по разделам динамического инлайн-меню.
    Поддерживает:
      - menu: целевой раздел ("main", "events", "event_detail", "top", "profile", "rules", "noop")
      - page: номер текущей страницы пагинации
      - item_id: идентификатор конкретного элемента (например, ID мероприятия)
    """
    menu: str
    page: int = 1
    item_id: Optional[int] = None


class EventAction(CallbackData, prefix="evt"):
    """
    Типизированная фабрика для действий с мероприятием (выбор роли, подтверждение, подача заявки).
    Поддерживает:
      - action: тип действия ("choose_role", "confirm", "submit")
      - event_id: ID мероприятия
      - role: выбранная роль ("participant", "helper", "organizer")
      - page: номер страницы для возврата к списку
    """
    action: str
    event_id: int
    role: Optional[str] = None
    page: int = 1
