import enum
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot.database.base import Base


class EventType(str, enum.Enum):
    """Тип мероприятия."""
    ACADEMIC = "academic"
    EXTRACURRICULAR = "extracurricular"

    def label(self) -> str:
        if self == EventType.ACADEMIC:
            return "Учебное"
        return "Внеучебное"


class ApplicationRole(str, enum.Enum):
    """Роль студента на мероприятии."""
    PARTICIPANT = "participant"
    HELPER = "helper"
    ORGANIZER = "organizer"

    def label(self) -> str:
        labels = {
            ApplicationRole.PARTICIPANT: "Участник",
            ApplicationRole.HELPER: "Помощник",
            ApplicationRole.ORGANIZER: "Организатор",
        }
        return labels.get(self, str(self.value))


class ApplicationStatus(str, enum.Enum):
    """Статус заявки на участие."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    def label(self) -> str:
        labels = {
            ApplicationStatus.PENDING: "На рассмотрении ⏳",
            ApplicationStatus.APPROVED: "Одобрена ✅",
            ApplicationStatus.REJECTED: "Отклонена ❌",
        }
        return labels.get(self, str(self.value))


class Student(Base):
    """Модель студента."""
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_name: Mapped[str] = mapped_column(String(50), nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now(), nullable=False)

    # Связи
    applications: Mapped[List["Application"]] = relationship(
        "Application",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    points_history: Mapped[List["PointHistory"]] = relationship(
        "PointHistory",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="desc(PointHistory.created_at)",
    )

    def __repr__(self) -> str:
        return f"<Student(id={self.id}, full_name='{self.full_name}', points={self.total_points})>"


class Event(Base):
    """Модель мероприятия."""
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, native_enum=False),
        default=EventType.EXTRACURRICULAR,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Связи
    applications: Mapped[List["Application"]] = relationship(
        "Application",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title='{self.title}', active={self.is_active})>"


class Application(Base):
    """Модель заявки на участие в мероприятии."""
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[ApplicationRole] = mapped_column(
        Enum(ApplicationRole, native_enum=False),
        nullable=False,
    )
    points_calculated: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, native_enum=False),
        default=ApplicationStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now(), nullable=False)

    # Связи
    student: Mapped["Student"] = relationship("Student", back_populates="applications", lazy="joined")
    event: Mapped["Event"] = relationship("Event", back_populates="applications", lazy="joined")

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, student_id={self.student_id}, event_id={self.event_id}, status='{self.status}')>"


class PointHistory(Base):
    """Модель истории начисления/списания баллов."""
    __tablename__ = "point_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now(), nullable=False)

    # Связи
    student: Mapped["Student"] = relationship("Student", back_populates="points_history")

    def __repr__(self) -> str:
        return f"<PointHistory(id={self.id}, student_id={self.student_id}, amount={self.amount})>"
