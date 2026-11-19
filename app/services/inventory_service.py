from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import CurrencyInventory, InventoryMovement
from app.config import settings


def get_or_create_currency_inventory(db: Session, currency_code: str = "MYR", lock: bool = False) -> CurrencyInventory:
    query = db.query(CurrencyInventory).filter(CurrencyInventory.currency_code == currency_code)
    if lock:
        # If PostgreSQL, with_for_update() locks the row; SQLite ignores with_for_update safely
        query = query.with_for_update()
    inv = query.first()
    if not inv:
        inv = CurrencyInventory(
            currency_code=currency_code,
            total_quantity=Decimal("0.0000"),
            weighted_average_cost=Decimal("0.0000"),
            total_valuation_bdt=Decimal("0.00"),
        )
        db.add(inv)
        db.flush()
    return inv


def record_purchase_inflow(
    db: Session,
    quantity: Decimal,
    rate: Decimal,
    transaction_id: Optional[str] = None,
    currency_code: str = "MYR",
) -> Tuple[CurrencyInventory, InventoryMovement]:
    if quantity <= Decimal("0"):
        raise ValueError("Purchase quantity must be positive.")
    if rate <= Decimal("0"):
        raise ValueError("Purchase rate must be positive.")

    inv = get_or_create_currency_inventory(db, currency_code=currency_code, lock=True)

    inflow_cost = (quantity * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    new_quantity = inv.total_quantity + quantity
    new_valuation = (inv.total_valuation_bdt + inflow_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    new_wac = (new_valuation / new_quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    inv.total_quantity = new_quantity
    inv.total_valuation_bdt = new_valuation
    inv.weighted_average_cost = new_wac

    movement = InventoryMovement(
        inventory_id=inv.id,
        transaction_id=transaction_id,
        movement_type="PURCHASE_INFLOW",
        quantity_delta=quantity,
        unit_cost_bdt=rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        total_cost_bdt=inflow_cost,
        resulting_balance_qty=new_quantity,
        resulting_wac=new_wac,
    )
    db.add(movement)
    db.flush()
    return inv, movement


def record_sales_outflow(
    db: Session,
    quantity: Decimal,
    transaction_id: Optional[str] = None,
    currency_code: str = "MYR",
) -> Tuple[CurrencyInventory, InventoryMovement, Decimal]:
    if quantity <= Decimal("0"):
        raise ValueError("Sales quantity must be positive.")

    inv = get_or_create_currency_inventory(db, currency_code=currency_code, lock=True)

    if inv.total_quantity < quantity:
        raise ValueError(
            f"Insufficient {currency_code} inventory! Available: {inv.total_quantity:,.2f} {currency_code}, Requested: {quantity:,.2f} {currency_code}."
        )

    current_wac = inv.weighted_average_cost
    # Calculate COGS using moving WAC
    cogs = (quantity * current_wac).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    new_quantity = inv.total_quantity - quantity
    if new_quantity == Decimal("0"):
        new_valuation = Decimal("0.00")
        new_wac = Decimal("0.0000")
    else:
        new_valuation = (inv.total_valuation_bdt - cogs).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if new_valuation < Decimal("0"):
            new_valuation = Decimal("0.00")
        new_wac = current_wac  # WAC does not change on a sale

    inv.total_quantity = new_quantity
    inv.total_valuation_bdt = new_valuation
    inv.weighted_average_cost = new_wac

    movement = InventoryMovement(
        inventory_id=inv.id,
        transaction_id=transaction_id,
        movement_type="SALE_OUTFLOW",
        quantity_delta=-quantity,
        unit_cost_bdt=current_wac,
        total_cost_bdt=cogs,
        resulting_balance_qty=new_quantity,
        resulting_wac=new_wac,
    )
    db.add(movement)
    db.flush()
    return inv, movement, cogs


def record_reversal_adjustment(
    db: Session,
    quantity_delta: Decimal,
    unit_cost: Decimal,
    total_cost: Decimal,
    reversal_type: str,
    transaction_id: Optional[str] = None,
    currency_code: str = "MYR",
) -> Tuple[CurrencyInventory, InventoryMovement]:
    inv = get_or_create_currency_inventory(db, currency_code=currency_code, lock=True)
    new_quantity = inv.total_quantity + quantity_delta
    if new_quantity < Decimal("0"):
        raise ValueError(f"Reversal would cause negative {currency_code} inventory!")

    new_valuation = inv.total_valuation_bdt + (total_cost if quantity_delta > 0 else -total_cost)
    if new_valuation < Decimal("0"):
        new_valuation = Decimal("0.00")

    if new_quantity > Decimal("0"):
        new_wac = (new_valuation / new_quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        new_wac = Decimal("0.0000")

    inv.total_quantity = new_quantity
    inv.total_valuation_bdt = new_valuation
    inv.weighted_average_cost = new_wac

    movement = InventoryMovement(
        inventory_id=inv.id,
        transaction_id=transaction_id,
        movement_type=reversal_type,
        quantity_delta=quantity_delta,
        unit_cost_bdt=unit_cost,
        total_cost_bdt=total_cost,
        resulting_balance_qty=new_quantity,
        resulting_wac=new_wac,
    )
    db.add(movement)
    db.flush()
    return inv, movement


def get_inventory_summary(db: Session, currency_code: str = "MYR") -> dict:
    inv = get_or_create_currency_inventory(db, currency_code=currency_code)
    
    # Total purchased
    purchased_movements = db.query(InventoryMovement).filter(
        InventoryMovement.movement_type.in_(["PURCHASE_INFLOW", "REVERSAL_INFLOW"])
    ).all()
    total_purchased_qty = sum((m.quantity_delta for m in purchased_movements if m.quantity_delta > 0), Decimal("0"))
    
    # Total sold
    sold_movements = db.query(InventoryMovement).filter(
        InventoryMovement.movement_type.in_(["SALE_OUTFLOW", "REVERSAL_OUTFLOW"])
    ).all()
    total_sold_qty = sum((-m.quantity_delta for m in sold_movements if m.quantity_delta < 0), Decimal("0"))

    # Movement history
    recent_movements = (
        db.query(InventoryMovement)
        .order_by(desc(InventoryMovement.created_at))
        .limit(50)
        .all()
    )

    return {
        "currency_code": currency_code,
        "available_quantity": inv.total_quantity,
        "weighted_average_cost": inv.weighted_average_cost,
        "total_valuation_bdt": inv.total_valuation_bdt,
        "total_purchased_qty": total_purchased_qty,
        "total_sold_qty": total_sold_qty,
        "recent_movements": recent_movements,
    }
