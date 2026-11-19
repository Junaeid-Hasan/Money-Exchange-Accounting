from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import (
    Payment,
    Transaction,
    Customer,
    CashAccount,
    ChartOfAccount,
    AuditLog,
)
from app.models.base import get_utc_now
from app.services.cash_service import (
    record_cash_inflow,
    record_cash_outflow,
)
from app.services.accounting_service import post_journal_entry
from app.services.transaction_service import generate_payment_number


def record_incoming_payment(
    db: Session,
    transaction_id: str,
    amount: Decimal,
    cash_account_id: str,
    payment_method: str,
    created_by_id: str,
    payment_date: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Payment:
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero.")

    tx = db.query(Transaction).filter_by(id=transaction_id).with_for_update().first()
    if not tx:
        raise ValueError("Transaction not found.")
    if tx.transaction_type != "SALE":
        raise ValueError("Incoming payments can only be recorded against Sales transactions.")
    if tx.status == "CANCELLED":
        raise ValueError("Cannot record payment for a cancelled transaction.")

    if amount > tx.outstanding_amount_bdt:
        raise ValueError(
            f"Payment amount (৳{amount:,.2f}) exceeds outstanding receivable (৳{tx.outstanding_amount_bdt:,.2f})!"
        )

    customer = db.query(Customer).filter_by(id=tx.customer_id).with_for_update().first()
    cash_acc = db.query(CashAccount).filter_by(id=cash_account_id).first()
    if not cash_acc:
        raise ValueError("Invalid cash account.")

    p_date = payment_date or get_utc_now()
    p_num = generate_payment_number(db, p_date)

    payment = Payment(
        payment_number=p_num,
        payment_type="INCOMING",
        customer_id=customer.id,
        transaction_id=tx.id,
        amount_bdt=amount,
        cash_account_id=cash_acc.id,
        payment_method=payment_method,
        reference_note=notes,
        created_by_id=created_by_id,
        payment_date=p_date,
    )
    db.add(payment)

    # Update Transaction balances
    tx.paid_amount_bdt = (tx.paid_amount_bdt + amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tx.outstanding_amount_bdt = (tx.outstanding_amount_bdt - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if tx.outstanding_amount_bdt == Decimal("0.00"):
        tx.payment_status = "FULLY_PAID"
    else:
        tx.payment_status = "PARTIALLY_PAID"

    # Update Customer Receivable balance
    customer.total_receivable_bdt = max(
        Decimal("0.00"),
        (customer.total_receivable_bdt - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    # Cash Inflow
    record_cash_inflow(
        db=db,
        cash_account_id=cash_acc.id,
        amount=amount,
        reference_type="PAYMENT",
        reference_id=payment.id,
        notes=f"Customer installment payment for {tx.transaction_number}",
    )

    # Post Journal Entry:
    # DEBIT: Cash Account GL (amount)
    # CREDIT: 1030 Accounts Receivable (amount)
    cash_gl = db.query(ChartOfAccount).filter_by(id=cash_acc.gl_account_id).first()
    lines = [
        (cash_gl.account_code, amount, Decimal("0.00"), f"Installment payment for {tx.transaction_number}"),
        ("1030", Decimal("0.00"), amount, f"Receivable settlement by {customer.full_name} for {tx.transaction_number}"),
    ]

    post_journal_entry(
        db=db,
        entry_date=p_date.date(),
        reference_type="PAYMENT",
        reference_id=payment.id,
        description=f"Incoming Payment {payment.payment_number} from {customer.full_name} on {tx.transaction_number} (৳{amount:,.2f})",
        lines=lines,
        user_id=created_by_id,
    )

    audit = AuditLog(
        user_id=created_by_id,
        action="INCOMING_PAYMENT",
        entity_name="Payment",
        entity_id=payment.id,
        new_values={
            "payment_number": payment.payment_number,
            "tx_num": tx.transaction_number,
            "customer": customer.full_name,
            "amount": str(amount),
            "remaining_outstanding": str(tx.outstanding_amount_bdt),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(payment)
    return payment


def record_outgoing_payment(
    db: Session,
    transaction_id: str,
    amount: Decimal,
    cash_account_id: str,
    payment_method: str,
    created_by_id: str,
    payment_date: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Payment:
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero.")

    tx = db.query(Transaction).filter_by(id=transaction_id).with_for_update().first()
    if not tx:
        raise ValueError("Transaction not found.")
    if tx.transaction_type != "PURCHASE":
        raise ValueError("Outgoing payments can only be recorded against Purchase transactions.")
    if tx.status == "CANCELLED":
        raise ValueError("Cannot record payment for a cancelled transaction.")

    if amount > tx.outstanding_amount_bdt:
        raise ValueError(
            f"Payment amount (৳{amount:,.2f}) exceeds outstanding payable (৳{tx.outstanding_amount_bdt:,.2f})!"
        )

    customer = db.query(Customer).filter_by(id=tx.customer_id).with_for_update().first()
    cash_acc = db.query(CashAccount).filter_by(id=cash_account_id).first()
    if not cash_acc:
        raise ValueError("Invalid cash account.")

    p_date = payment_date or get_utc_now()
    p_num = generate_payment_number(db, p_date)

    payment = Payment(
        payment_number=p_num,
        payment_type="OUTGOING",
        customer_id=customer.id,
        transaction_id=tx.id,
        amount_bdt=amount,
        cash_account_id=cash_acc.id,
        payment_method=payment_method,
        reference_note=notes,
        created_by_id=created_by_id,
        payment_date=p_date,
    )
    db.add(payment)

    # Update Transaction balances
    tx.paid_amount_bdt = (tx.paid_amount_bdt + amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tx.outstanding_amount_bdt = (tx.outstanding_amount_bdt - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if tx.outstanding_amount_bdt == Decimal("0.00"):
        tx.payment_status = "FULLY_PAID"
    else:
        tx.payment_status = "PARTIALLY_PAID"

    # Update Customer Payable balance
    customer.total_payable_bdt = max(
        Decimal("0.00"),
        (customer.total_payable_bdt - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    # Cash Outflow
    record_cash_outflow(
        db=db,
        cash_account_id=cash_acc.id,
        amount=amount,
        reference_type="PAYMENT",
        reference_id=payment.id,
        notes=f"Company installment payout for {tx.transaction_number}",
    )

    # Post Journal Entry:
    # DEBIT: 2010 Accounts Payable (amount)
    # CREDIT: Cash Account GL (amount)
    cash_gl = db.query(ChartOfAccount).filter_by(id=cash_acc.gl_account_id).first()
    lines = [
        ("2010", amount, Decimal("0.00"), f"Payable settlement to {customer.full_name} for {tx.transaction_number}"),
        (cash_gl.account_code, Decimal("0.00"), amount, f"Installment payout for {tx.transaction_number}"),
    ]

    post_journal_entry(
        db=db,
        entry_date=p_date.date(),
        reference_type="PAYMENT",
        reference_id=payment.id,
        description=f"Outgoing Payment {payment.payment_number} to {customer.full_name} on {tx.transaction_number} (৳{amount:,.2f})",
        lines=lines,
        user_id=created_by_id,
    )

    audit = AuditLog(
        user_id=created_by_id,
        action="OUTGOING_PAYMENT",
        entity_name="Payment",
        entity_id=payment.id,
        new_values={
            "payment_number": payment.payment_number,
            "tx_num": tx.transaction_number,
            "customer": customer.full_name,
            "amount": str(amount),
            "remaining_outstanding": str(tx.outstanding_amount_bdt),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(payment)
    return payment


def record_mutual_balance_settlement(
    db: Session,
    customer_id: str,
    amount: Decimal,
    created_by_id: str,
    notes: Optional[str] = None,
) -> dict:
    """
    Explicit authorized cross-settlement between Accounts Payable and Accounts Receivable
    for a customer who is both a debtor and a creditor.
    """
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= Decimal("0"):
        raise ValueError("Settlement amount must be positive.")

    customer = db.query(Customer).filter_by(id=customer_id).with_for_update().first()
    if not customer:
        raise ValueError("Customer not found.")

    if amount > customer.total_receivable_bdt:
        raise ValueError(f"Settlement amount exceeds customer receivable balance (৳{customer.total_receivable_bdt:,.2f})!")
    if amount > customer.total_payable_bdt:
        raise ValueError(f"Settlement amount exceeds customer payable balance (৳{customer.total_payable_bdt:,.2f})!")

    customer.total_receivable_bdt = (customer.total_receivable_bdt - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    customer.total_payable_bdt = (customer.total_payable_bdt - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Post Bilateral Journal Entry:
    # DEBIT: 2010 Accounts Payable
    # CREDIT: 1030 Accounts Receivable
    lines = [
        ("2010", amount, Decimal("0.00"), f"Mutual settlement AP offset for {customer.full_name}"),
        ("1030", Decimal("0.00"), amount, f"Mutual settlement AR offset for {customer.full_name}"),
    ]

    je = post_journal_entry(
        db=db,
        entry_date=datetime.now(timezone.utc).date(),
        reference_type="SETTLEMENT",
        reference_id=customer.id,
        description=f"Mutual balance offset for {customer.full_name} (৳{amount:,.2f}). {notes or ''}",
        lines=lines,
        user_id=created_by_id,
    )

    audit = AuditLog(
        user_id=created_by_id,
        action="MUTUAL_SETTLEMENT",
        entity_name="Customer",
        entity_id=customer.id,
        new_values={
            "customer": customer.full_name,
            "settled_amount": str(amount),
            "new_receivable": str(customer.total_receivable_bdt),
            "new_payable": str(customer.total_payable_bdt),
        },
    )
    db.add(audit)
    db.commit()

    return {
        "customer": customer,
        "settled_amount": amount,
        "journal_entry": je,
    }
