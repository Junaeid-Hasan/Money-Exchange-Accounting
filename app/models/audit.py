from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, get_utc_now


class AuditLog(Base, UUIDMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, LOGIN, VOID
    entity_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Transaction, Customer, Rate, etc.
    entity_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    old_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)

    user: Mapped[Optional["User"]] = relationship("User")
