from decimal import Decimal
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class ExchangeRate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        CheckConstraint("default_purchase_rate > 0", name="chk_purchase_rate_positive"),
        CheckConstraint("default_selling_rate > 0", name="chk_selling_rate_positive"),
    )

    currency_code: Mapped[str] = mapped_column(String(10), default="MYR", index=True, nullable=False)
    default_purchase_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    default_selling_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    created_by_user: Mapped["User"] = relationship("User")
