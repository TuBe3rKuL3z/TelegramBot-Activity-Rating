from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния первичной регистрации пользователя."""
    waiting_for_full_name = State()
    waiting_for_group = State()


class StudentApplicationStates(StatesGroup):
    """Состояния подачи заявки на участие в мероприятии."""
    selecting_event = State()
    selecting_role = State()
    confirming = State()


class AdminEventStates(StatesGroup):
    """Состояния создания нового мероприятия администратором."""
    waiting_for_title = State()
    waiting_for_date = State()
    waiting_for_type = State()


class AdminManualPointsStates(StatesGroup):
    """Состояния ручного начисления/списания баллов."""
    waiting_for_student_query = State()
    selecting_student = State()
    waiting_for_amount = State()
    waiting_for_reason = State()


class AdminReviewStates(StatesGroup):
    """Состояния модерации заявок администратором."""
    waiting_for_custom_points = State()
    waiting_for_reject_reason = State()
