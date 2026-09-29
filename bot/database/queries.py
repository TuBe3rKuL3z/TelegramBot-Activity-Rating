from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import (
    Application,
    ApplicationRole,
    ApplicationStatus,
    Event,
    EventType,
    PointHistory,
    Student,
)


# ==========================================
# СТУДЕНТЫ (STUDENTS)
# ==========================================

async def get_student_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Student]:
    """Получить студента по его Telegram ID."""
    stmt = select(Student).where(Student.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_student_by_id(session: AsyncSession, student_id: int) -> Optional[Student]:
    """Получить студента по первичному ключу ID."""
    stmt = select(Student).where(Student.id == student_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_student(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    group_name: str,
    is_admin: bool = False,
) -> Student:
    """Создать нового студента при первой регистрации."""
    student = Student(
        telegram_id=telegram_id,
        full_name=full_name.strip(),
        group_name=group_name.strip(),
        is_admin=is_admin,
        total_points=0,
    )
    session.add(student)
    await session.commit()
    await session.refresh(student)
    return student


async def update_student_admin_status(
    session: AsyncSession,
    telegram_id: int,
    is_admin: bool,
) -> Optional[Student]:
    """Обновить статус администратора для пользователя."""
    student = await get_student_by_telegram_id(session, telegram_id)
    if student:
        student.is_admin = is_admin
        await session.commit()
        await session.refresh(student)
    return student


async def get_top_students(session: AsyncSession, limit: int = 10) -> List[Student]:
    """Получить топ студентов по баллам."""
    stmt = select(Student).order_by(desc(Student.total_points), Student.full_name).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_paginated_top_students(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 5,
) -> tuple[List[Student], int, int]:
    """Получить топ студентов с пагинацией (список студентов, общее количество, всего страниц)."""
    count_stmt = select(func.count(Student.id))
    total_count = (await session.execute(count_stmt)).scalar_one() or 0
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size

    stmt = (
        select(Student)
        .order_by(desc(Student.total_points), Student.full_name)
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total_count, total_pages


async def get_student_rank_and_stats(session: AsyncSession, student_id: int) -> Dict[str, Any]:
    """
    Рассчитать место студента в общем зачете и баллы за текущий календарный месяц.
    """
    student = await get_student_by_id(session, student_id)
    if not student:
        return {"rank": 0, "total_points": 0, "month_points": 0, "total_students": 0}

    # Подсчет общего количества студентов
    total_students_res = await session.execute(select(func.count(Student.id)))
    total_students = total_students_res.scalar_one() or 1

    # Подсчет места: количество студентов, у которых больше баллов + 1
    rank_res = await session.execute(
        select(func.count(Student.id)).where(Student.total_points > student.total_points)
    )
    rank = (rank_res.scalar_one() or 0) + 1

    # Подсчет баллов за текущий месяц из PointHistory
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)

    month_points_res = await session.execute(
        select(func.coalesce(func.sum(PointHistory.amount), 0)).where(
            PointHistory.student_id == student_id,
            PointHistory.created_at >= start_of_month,
        )
    )
    month_points = month_points_res.scalar_one() or 0

    return {
        "rank": rank,
        "total_points": student.total_points,
        "month_points": month_points,
        "total_students": total_students,
    }


async def search_students(session: AsyncSession, query_str: str, limit: int = 10) -> List[Student]:
    """Поиск студентов по ФИО, группе или Telegram ID."""
    clean_query = query_str.strip()
    filters = [
        Student.full_name.ilike(f"%{clean_query}%"),
        Student.group_name.ilike(f"%{clean_query}%"),
    ]
    if clean_query.isdigit():
        filters.append(Student.telegram_id == int(clean_query))

    stmt = select(Student).where(or_(*filters)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def add_points_to_student(
    session: AsyncSession,
    student_id: int,
    amount: int,
    reason: str,
) -> Optional[Student]:
    """Начислить или списать баллы студенту с записью в историю."""
    student = await get_student_by_id(session, student_id)
    if not student:
        return None

    student.total_points += amount
    history = PointHistory(
        student_id=student.id,
        amount=amount,
        reason=reason.strip(),
    )
    session.add(history)
    await session.commit()
    await session.refresh(student)
    return student


# ==========================================
# МЕРОПРИЯТИ (EVENTS)
# ==========================================

async def create_event(
    session: AsyncSession,
    title: str,
    event_date: datetime,
    event_type: EventType,
    is_active: bool = True,
) -> Event:
    """Создать новое мероприятие."""
    event = Event(
        title=title.strip(),
        event_date=event_date,
        event_type=event_type,
        is_active=is_active,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def get_active_events(session: AsyncSession) -> List[Event]:
    """Получить список всех активных мероприятий."""
    stmt = select(Event).where(Event.is_active == True).order_by(Event.event_date.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_paginated_active_events(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 4,
) -> tuple[List[Event], int, int]:
    """Получить список активных мероприятий с пагинацией (мероприятия, общее число, число страниц)."""
    count_stmt = select(func.count(Event.id)).where(Event.is_active == True)
    total_count = (await session.execute(count_stmt)).scalar_one() or 0
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size

    stmt = (
        select(Event)
        .where(Event.is_active == True)
        .order_by(Event.event_date.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all()), total_count, total_pages


async def get_all_events(session: AsyncSession, limit: int = 50) -> List[Event]:
    """Получить список мероприятий с ограничением."""
    stmt = select(Event).order_by(Event.event_date.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_event_by_id(session: AsyncSession, event_id: int) -> Optional[Event]:
    """Получить мероприятие по ID."""
    stmt = select(Event).where(Event.id == event_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def toggle_event_status(session: AsyncSession, event_id: int) -> Optional[Event]:
    """Переключить статус активности мероприятия."""
    event = await get_event_by_id(session, event_id)
    if event:
        event.is_active = not event.is_active
        await session.commit()
        await session.refresh(event)
    return event


# ==========================================
# ЗАЯВКИ (APPLICATIONS)
# ==========================================

async def get_existing_application(
    session: AsyncSession,
    student_id: int,
    event_id: int,
) -> Optional[Application]:
    """Проверить, подавал ли уже студент заявку на это мероприятие."""
    stmt = select(Application).where(
        Application.student_id == student_id,
        Application.event_id == event_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_application(
    session: AsyncSession,
    student_id: int,
    event_id: int,
    role: ApplicationRole,
    points_calculated: int,
) -> Application:
    """Создать заявку на участие в мероприятии."""
    application = Application(
        student_id=student_id,
        event_id=event_id,
        role=role,
        points_calculated=points_calculated,
        status=ApplicationStatus.PENDING,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


async def get_application_by_id(session: AsyncSession, app_id: int) -> Optional[Application]:
    """Получить заявку со связанными объектами Student и Event."""
    stmt = select(Application).where(Application.id == app_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_pending_applications(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 1,
) -> List[Application]:
    """Получить заявки в статусе pending (постранично)."""
    stmt = (
        select(Application)
        .where(Application.status == ApplicationStatus.PENDING)
        .order_by(Application.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_pending_applications(session: AsyncSession) -> int:
    """Подсчет общего числа заявок на модерации."""
    stmt = select(func.count(Application.id)).where(Application.status == ApplicationStatus.PENDING)
    result = await session.execute(stmt)
    return result.scalar_one() or 0


async def approve_application(
    session: AsyncSession,
    app_id: int,
    custom_points: Optional[int] = None,
) -> Optional[Application]:
    """
    Одобрить заявку:
    - меняет статус на approved
    - начисляет баллы студенту
    - создает запись в PointHistory
    """
    application = await get_application_by_id(session, app_id)
    if not application or application.status != ApplicationStatus.PENDING:
        return None

    points_to_add = custom_points if custom_points is not None else application.points_calculated
    application.points_calculated = points_to_add
    application.status = ApplicationStatus.APPROVED

    student = application.student
    student.total_points += points_to_add

    event_title = application.event.title if application.event else "Мероприятие"
    role_name = application.role.label()

    history = PointHistory(
        student_id=student.id,
        amount=points_to_add,
        reason=f"Участие в '{event_title}' ({role_name})",
    )
    session.add(history)
    await session.commit()
    await session.refresh(application)
    return application


async def reject_application(
    session: AsyncSession,
    app_id: int,
    reason: Optional[str] = None,
) -> Optional[Application]:
    """Отклонить заявку."""
    application = await get_application_by_id(session, app_id)
    if not application or application.status != ApplicationStatus.PENDING:
        return None

    application.status = ApplicationStatus.REJECTED
    await session.commit()
    await session.refresh(application)
    return application


# ==========================================
# СТАТИСТИКА (STATISTICS)
# ==========================================

async def get_general_statistics(session: AsyncSession) -> Dict[str, Any]:
    """Получить общую сводную статистику системы."""
    total_students = (await session.execute(select(func.count(Student.id)))).scalar_one() or 0
    total_events = (await session.execute(select(func.count(Event.id)))).scalar_one() or 0
    active_events = (
        await session.execute(select(func.count(Event.id)).where(Event.is_active == True))
    ).scalar_one() or 0

    pending_apps = (
        await session.execute(
            select(func.count(Application.id)).where(Application.status == ApplicationStatus.PENDING)
        )
    ).scalar_one() or 0

    approved_apps = (
        await session.execute(
            select(func.count(Application.id)).where(Application.status == ApplicationStatus.APPROVED)
        )
    ).scalar_one() or 0

    rejected_apps = (
        await session.execute(
            select(func.count(Application.id)).where(Application.status == ApplicationStatus.REJECTED)
        )
    ).scalar_one() or 0

    total_points = (
        await session.execute(
            select(func.coalesce(func.sum(PointHistory.amount), 0)).where(PointHistory.amount > 0)
        )
    ).scalar_one() or 0

    return {
        "total_students": total_students,
        "total_events": total_events,
        "active_events": active_events,
        "pending_apps": pending_apps,
        "approved_apps": approved_apps,
        "rejected_apps": rejected_apps,
        "total_points": total_points,
    }
