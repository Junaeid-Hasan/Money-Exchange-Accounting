from decimal import Decimal
from datetime import date
from typing import Optional
from sqlalchemy import String, Numeric, Date, Boolean, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class ChartOfAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "chart_of_accounts"

    account_code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # ASSET, LIABILITY, EQUITY, INCOME, EXPENSE
    normal_balance: Mapped[str] = mapped_column(String(6), nullable=False)  # DEBIT, CREDIT
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    journal_lines: Mapped[list["JournalEntryLine"]] = relationship("JournalEntryLine", back_populates="account")


class JournalEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "journal_entries"

    entry_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)  # PURCHASE, SALE, PAYMENT, EXPENSE, REVERSAL, ADJUSTMENT
    reference_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reversed_by_entry_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("journal_entries.id"), nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    lines: Mapped[list["JournalEntryLine"]] = relationship("JournalEntryLine", back_populates="journal_entry", cascade="all, delete-orphan")
    created_by_user: Mapped["User"] = relationship("User")


class JournalEntryLine(Base, UUIDMixin):
    __tablename__ = "journal_entry_lines"
    __table_args__ = (
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="chk_line_debit_xor_credit"
        ),
    )

    journal_entry_id: Mapped[str] = mapped_column(String(36), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("chart_of_accounts.id"), nullable=False, index=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    line_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    journal_entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["ChartOfAccount"] = relationship("ChartOfAccount", back_populates="journal_lines")
