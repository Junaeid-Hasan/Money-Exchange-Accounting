from decimal import Decimal
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Transaction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("myr_quantity > 0", name="chk_tx_qty_positive"),
        CheckConstraint("exchange_rate > 0", name="chk_tx_rate_positive"),
        CheckConstraint("total_amount_bdt >= 0", name="chk_tx_total_non_negative"),
        CheckConstraint("paid_amount_bdt >= 0", name="chk_tx_paid_non_negative"),
        CheckConstraint("outstanding_amount_bdt >= 0", name="chk_tx_outstanding_non_negative"),
    )

    transaction_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), index=True, nullable=False)  # 'PURCHASE' or 'SALE'
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(10), default="MYR", nullable=False)
    myr_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_amount_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    paid_amount_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    outstanding_amount_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cogs_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="UNPAID", index=True, nullable=False)  # UNPAID, PARTIALLY_PAID, FULLY_PAID
    status: Mapped[str] = mapped_column(String(20), default="POSTED", index=True, nullable=False)  # POSTED, CANCELLED, REVERSED
    payment_method: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # CASH, BANK_TRANSFER, MFS
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="transactions")
    created_by_user: Mapped["User"] = relationship("User", back_populates="transactions")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="transaction")
    inventory_movement: Mapped[Optional["InventoryMovement"]] = relationship("InventoryMovement", back_populates="transaction", uselist=False)
