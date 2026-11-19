from decimal import Decimal
from datetime import date
from typing import Optional
from sqlalchemy import String, Numeric, Date, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class ExpenseCategory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "expense_categories"

    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    gl_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("chart_of_accounts.id"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    gl_account: Mapped["ChartOfAccount"] = relationship("ChartOfAccount")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="category")


class Expense(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_bdt > 0", name="chk_expense_amount_positive"),
    )

    expense_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("expense_categories.id"), nullable=False, index=True)
    amount_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cash_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("cash_accounts.id"), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_file_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="POSTED", index=True, nullable=False)  # POSTED, VOIDED
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    category: Mapped["ExpenseCategory"] = relationship("ExpenseCategory", back_populates="expenses")
    cash_account: Mapped["CashAccount"] = relationship("CashAccount")
    created_by_user: Mapped["User"] = relationship("User")
