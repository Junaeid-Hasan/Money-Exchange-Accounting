from decimal import Decimal
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Payment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_bdt > 0", name="chk_payment_amount_positive"),
    )

    payment_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    payment_type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # 'INCOMING' or 'OUTGOING'
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=False, index=True)
    amount_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cash_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("cash_accounts.id"), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)  # CASH, BANK_TRANSFER, MFS
    reference_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="payments")
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="payments")
    created_by_user: Mapped["User"] = relationship("User", back_populates="payments")
    cash_account: Mapped["CashAccount"] = relationship("CashAccount")
