from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Text, Boolean, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Customer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("total_receivable_bdt >= 0", name="chk_cust_receivable_non_negative"),
        CheckConstraint("total_payable_bdt >= 0", name="chk_cust_payable_non_negative"),
    )

    customer_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(25), index=True, nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Financial Balances tracked independently
    total_receivable_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    total_payable_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="customer")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="customer")
