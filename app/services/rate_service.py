from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import ExchangeRate, AuditLog
from app.models.base import get_utc_now


def get_current_exchange_rate(db: Session, currency_code: str = "MYR") -> Optional[ExchangeRate]:
    return (
        db.query(ExchangeRate)
        .filter(ExchangeRate.currency_code == currency_code, ExchangeRate.is_active == True)
        .order_by(desc(ExchangeRate.effective_from))
        .first()
    )


def update_exchange_rates(
    db: Session,
    purchase_rate: Decimal,
    selling_rate: Decimal,
    user_id: str,
    currency_code: str = "MYR",
) -> ExchangeRate:
    if purchase_rate <= Decimal("0"):
        raise ValueError("Purchase rate must be strictly positive.")
    if selling_rate <= Decimal("0"):
        raise ValueError("Selling rate must be strictly positive.")
    if selling_rate < purchase_rate:
        # Business warning / alert
        pass

    now = get_utc_now()

    # Deactivate current rate if any
    current_rate = get_current_exchange_rate(db, currency_code)
    old_data = None
    if current_rate:
        current_rate.is_active = False
        current_rate.effective_to = now
        old_data = {
            "purchase_rate": str(current_rate.default_purchase_rate),
            "selling_rate": str(current_rate.default_selling_rate),
        }

    # Create new active rate record
    new_rate = ExchangeRate(
        currency_code=currency_code,
        default_purchase_rate=purchase_rate,
        default_selling_rate=selling_rate,
        effective_from=now,
        effective_to=None,
        is_active=True,
        created_by_id=user_id,
    )
    db.add(new_rate)
    db.flush()

    audit = AuditLog(
        user_id=user_id,
        action="UPDATE_RATES",
        entity_name="ExchangeRate",
        entity_id=new_rate.id,
        old_values=old_data,
        new_values={
            "purchase_rate": str(purchase_rate),
            "selling_rate": str(selling_rate),
            "effective_from": now.isoformat(),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(new_rate)
    return new_rate


def get_rate_history(db: Session, currency_code: str = "MYR", limit: int = 50) -> List[ExchangeRate]:
    return (
        db.query(ExchangeRate)
        .filter(ExchangeRate.currency_code == currency_code)
        .order_by(desc(ExchangeRate.effective_from))
        .limit(limit)
        .all()
    )
