from typing import Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class CompanySettings(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "company_settings"

    company_name: Mapped[str] = mapped_column(String(150), default="Forex Exchange Bangladesh Ltd.", nullable=False)
    base_currency: Mapped[str] = mapped_column(String(10), default="BDT", nullable=False)
    primary_foreign_currency: Mapped[str] = mapped_column(String(10), default="MYR", nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(40), default="+880 1700-000000", nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), default="contact@forex-exchange.com.bd", nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, default="Motijheel Commercial Area, Dhaka, Bangladesh", nullable=True)
    trade_license_number: Mapped[Optional[str]] = mapped_column(String(60), default="TRAD/DNCC/012345/2026", nullable=True)
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Dhaka", nullable=False)
    receipt_footer_note: Mapped[Optional[str]] = mapped_column(Text, default="Thank you for trading with us. Please count your cash and foreign currency before leaving the counter.", nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
