from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class CurrencyInventory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "currency_inventory"
    __table_args__ = (
        CheckConstraint("total_quantity >= 0", name="chk_inventory_qty_non_negative"),
        CheckConstraint("weighted_average_cost >= 0", name="chk_inventory_wac_non_negative"),
        CheckConstraint("total_valuation_bdt >= 0", name="chk_inventory_valuation_non_negative"),
    )

    currency_code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False, default="MYR")
    total_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    weighted_average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.0000"), nullable=False)
    total_valuation_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)

    movements: Mapped[list["InventoryMovement"]] = relationship("InventoryMovement", back_populates="inventory")


class InventoryMovement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "inventory_movements"

    inventory_id: Mapped[str] = mapped_column(String(36), ForeignKey("currency_inventory.id"), nullable=False)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True, index=True)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)  # PURCHASE_INFLOW, SALE_OUTFLOW, REVERSAL_INFLOW, REVERSAL_OUTFLOW, ADJUSTMENT
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_cost_bdt: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    resulting_balance_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    resulting_wac: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    inventory: Mapped["CurrencyInventory"] = relationship("CurrencyInventory", back_populates="movements")
    transaction: Mapped[Optional["Transaction"]] = relationship("Transaction", back_populates="inventory_movement")
