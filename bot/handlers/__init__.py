from bot.handlers.admin import router as admin_router
from bot.handlers.common import router as common_router
from bot.handlers.menu import router as menu_router
from bot.handlers.student import router as student_router

__all__ = ["common_router", "menu_router", "student_router", "admin_router"]
