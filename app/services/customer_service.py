from typing import Optional, List, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from app.models import Customer, Transaction, Payment, AuditLog


def generate_customer_code(db: Session) -> str:
    count = db.query(Customer).count()
    return f"CUST-{(count + 1):05d}"


def create_customer(
    db: Session,
    full_name: str,
    phone_number: str,
    address: Optional[str] = None,
    national_id: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Customer:
    code = generate_customer_code(db)
    # Check code uniqueness just in case
    while db.query(Customer).filter_by(customer_code=code).first():
        count = int(code.split("-")[1]) + 1
        code = f"CUST-{count:05d}"

    customer = Customer(
        customer_code=code,
        full_name=full_name.strip(),
        phone_number=phone_number.strip(),
        address=address.strip() if address else None,
        national_id=national_id.strip() if national_id else None,
        notes=notes.strip() if notes else None,
        total_receivable_bdt=Decimal("0.00"),
        total_payable_bdt=Decimal("0.00"),
        is_archived=False,
    )
    db.add(customer)
    db.flush()

    # Audit log
    audit = AuditLog(
        user_id=user_id,
        action="CREATE",
        entity_name="Customer",
        entity_id=customer.id,
        new_values={
            "customer_code": customer.customer_code,
            "full_name": customer.full_name,
            "phone_number": customer.phone_number,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(
    db: Session,
    customer_id: str,
    full_name: str,
    phone_number: str,
    address: Optional[str] = None,
    national_id: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[Customer]:
    customer = db.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        return None

    old_data = {
        "full_name": customer.full_name,
        "phone_number": customer.phone_number,
        "address": customer.address,
        "national_id": customer.national_id,
        "notes": customer.notes,
    }

    customer.full_name = full_name.strip()
    customer.phone_number = phone_number.strip()
    customer.address = address.strip() if address else None
    customer.national_id = national_id.strip() if national_id else None
    customer.notes = notes.strip() if notes else None

    audit = AuditLog(
        user_id=user_id,
        action="UPDATE",
        entity_name="Customer",
        entity_id=customer.id,
        old_values=old_data,
        new_values={
            "full_name": customer.full_name,
            "phone_number": customer.phone_number,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(customer)
    return customer


def archive_customer(db: Session, customer_id: str, user_id: Optional[str] = None) -> bool:
    customer = db.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        return False
    customer.is_archived = True
    audit = AuditLog(
        user_id=user_id,
        action="ARCHIVE",
        entity_name="Customer",
        entity_id=customer.id,
        new_values={"is_archived": True},
    )
    db.add(audit)
    db.commit()
    return True


def list_customers(
    db: Session,
    search_query: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[Customer], int]:
    query = db.query(Customer)
    if not include_archived:
        query = query.filter(Customer.is_archived == False)

    if search_query:
        term = f"%{search_query.strip()}%"
        query = query.filter(
            or_(
                Customer.full_name.ilike(term),
                Customer.phone_number.ilike(term),
                Customer.customer_code.ilike(term),
                Customer.national_id.ilike(term),
            )
        )

    total_count = query.count()
    customers = query.order_by(desc(Customer.created_at)).offset(offset).limit(limit).all()
    return customers, total_count


def get_customer_profile_summary(db: Session, customer_id: str) -> Optional[dict]:
    customer = db.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        return None

    # Transactions
    txs = db.query(Transaction).filter_by(customer_id=customer_id).order_by(desc(Transaction.transaction_date)).all()
    # Payments
    payments = db.query(Payment).filter_by(customer_id=customer_id).order_by(desc(Payment.payment_date)).all()

    total_myr_sold_to_co = sum((t.myr_quantity for t in txs if t.transaction_type == "PURCHASE" and t.status != "CANCELLED"), Decimal("0"))
    total_myr_purchased_from_co = sum((t.myr_quantity for t in txs if t.transaction_type == "SALE" and t.status != "CANCELLED"), Decimal("0"))

    total_purchase_val = sum((t.total_amount_bdt for t in txs if t.transaction_type == "PURCHASE" and t.status != "CANCELLED"), Decimal("0"))
    total_sales_val = sum((t.total_amount_bdt for t in txs if t.transaction_type == "SALE" and t.status != "CANCELLED"), Decimal("0"))

    # Payments received by company from customer (incoming)
    payments_received = sum((p.amount_bdt for p in payments if p.payment_type == "INCOMING"), Decimal("0"))
    # Payments made by company to customer (outgoing)
    payments_made = sum((p.amount_bdt for p in payments if p.payment_type == "OUTGOING"), Decimal("0"))

    # Also include initial downpayments recorded on the transaction themselves if not logged as separate payment rows
    # In our engine, we will record every payment (including initial downpayment) as a Payment row or keep paid_amount_bdt synchronized.

    net_customer_balance = customer.total_receivable_bdt - customer.total_payable_bdt

    # Chronological Ledger Construction
    ledger_entries = []
    for t in txs:
        if t.transaction_type == "PURCHASE":
            ledger_entries.append({
                "date": t.transaction_date,
                "type": "PURCHASE",
                "ref": t.transaction_number,
                "description": f"Customer sold {t.myr_quantity:,.2f} MYR @ ৳{t.exchange_rate:,.2f}",
                "debit_bdt": Decimal("0.00"),
                "credit_bdt": t.total_amount_bdt,  # Company owes customer
                "paid_bdt": t.paid_amount_bdt,
                "status": t.payment_status,
            })
        else:
            ledger_entries.append({
                "date": t.transaction_date,
                "type": "SALE",
                "ref": t.transaction_number,
                "description": f"Customer purchased {t.myr_quantity:,.2f} MYR @ ৳{t.exchange_rate:,.2f}",
                "debit_bdt": t.total_amount_bdt,  # Customer owes company
                "credit_bdt": Decimal("0.00"),
                "paid_bdt": t.paid_amount_bdt,
                "status": t.payment_status,
            })

    for p in payments:
        if p.payment_type == "INCOMING":
            ledger_entries.append({
                "date": p.payment_date,
                "type": "INCOMING_PAYMENT",
                "ref": p.payment_number,
                "description": f"Customer payment received via {p.payment_method} ({p.reference_note or 'Installment'})",
                "debit_bdt": Decimal("0.00"),
                "credit_bdt": p.amount_bdt,  # Reduces receivable
                "paid_bdt": p.amount_bdt,
                "status": "SETTLED",
            })
        else:
            ledger_entries.append({
                "date": p.payment_date,
                "type": "OUTGOING_PAYMENT",
                "ref": p.payment_number,
                "description": f"Company paid customer via {p.payment_method} ({p.reference_note or 'Installment'})",
                "debit_bdt": p.amount_bdt,  # Reduces payable
                "credit_bdt": Decimal("0.00"),
                "paid_bdt": p.amount_bdt,
                "status": "SETTLED",
            })

    ledger_entries.sort(key=lambda x: x["date"], reverse=True)

    return {
        "customer": customer,
        "transactions": txs,
        "payments": payments,
        "ledger_entries": ledger_entries,
        "total_myr_sold_to_co": total_myr_sold_to_co,
        "total_myr_purchased_from_co": total_myr_purchased_from_co,
        "total_purchase_val": total_purchase_val,
        "total_sales_val": total_sales_val,
        "payments_received": payments_received,
        "payments_made": payments_made,
        "receivable_bdt": customer.total_receivable_bdt,
        "payable_bdt": customer.total_payable_bdt,
        "net_balance_bdt": net_customer_balance,
    }
