from decimal import Decimal
from datetime import date
from typing import Optional
from sqlalchemy import String, Numeric, Date, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class CashAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cash_accounts"

    account_code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # CASH, BANK, MFS
    gl_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("chart_of_accounts.id"), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)

    gl_account: Mapped["ChartOfAccount"] = relationship("ChartOfAccount")
    movements: Mapped[list["CashMovement"]] = relationship("CashMovement", back_populates="cash_account")


class CashMovement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cash_movements"

    cash_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("cash_accounts.id"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)  # INFLOW, OUTFLOW
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)  # PURCHASE, SALE, PAYMENT, EXPENSE, TRANSFER, RECONCILIATION
    reference_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    cash_account: Mapped["CashAccount"] = relationship("CashAccount", back_populates="movements")


class DailyCashReconciliation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "daily_cash_reconciliations"

    reconciliation_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    cash_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("cash_accounts.id"), nullable=False)
    system_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    physical_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discrepancy: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # physical - system
    status: Mapped[str] = mapped_column(String(30), default="BALANCED", nullable=False)  # BALANCED, DISCREPANCY_RECORDED
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reconciled_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    cash_account: Mapped["CashAccount"] = relationship("CashAccount")
    reconciled_by_user: Mapped["User"] = relationship("User")
