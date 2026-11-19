from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import (
    Transaction,
    Customer,
    CashAccount,
    Payment,
    AuditLog,
    ChartOfAccount,
)
from app.models.base import get_utc_now
from app.services.inventory_service import (
    record_purchase_inflow,
    record_sales_outflow,
    record_reversal_adjustment,
)
from app.services.cash_service import (
    record_cash_inflow,
    record_cash_outflow,
)
from app.services.accounting_service import (
    post_journal_entry,
    reverse_journal_entry,
)


def generate_transaction_number(db: Session, tx_type: str, tx_date: datetime) -> str:
    prefix = f"{'PUR' if tx_type == 'PURCHASE' else 'SAL'}-{tx_date.strftime('%Y%m%d')}"
    count = db.query(Transaction).filter(Transaction.transaction_number.like(f"{prefix}%")).count()
    return f"{prefix}-{(count + 1):04d}"


def generate_payment_number(db: Session, p_date: datetime) -> str:
    prefix = f"PAY-{p_date.strftime('%Y%m%d')}"
    count = db.query(Payment).filter(Payment.payment_number.like(f"{prefix}%")).count()
    return f"{prefix}-{(count + 1):04d}"


def create_purchase_transaction(
    db: Session,
    customer_id: str,
    myr_quantity: Decimal,
    purchase_rate: Decimal,
    initial_payment: Decimal,
    cash_account_id: str,
    payment_method: str,
    created_by_id: str,
    transaction_date: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Transaction:
    if myr_quantity <= Decimal("0"):
        raise ValueError("MYR Quantity must be positive.")
    if purchase_rate <= Decimal("0"):
        raise ValueError("Purchase Rate must be positive.")

    customer = db.query(Customer).filter_by(id=customer_id).with_for_update().first()
    if not customer:
        raise ValueError("Customer not found.")
    if customer.is_archived:
        raise ValueError("Cannot perform transactions for an archived customer.")

    cash_acc = db.query(CashAccount).filter_by(id=cash_account_id).first()
    if not cash_acc:
        raise ValueError("Invalid Cash/Bank account selected.")

    tx_date = transaction_date or get_utc_now()
    total_amount_bdt = (myr_quantity * purchase_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    initial_payment = initial_payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if initial_payment < Decimal("0"):
        raise ValueError("Payment amount cannot be negative.")
    if initial_payment > total_amount_bdt:
        raise ValueError(f"Initial payment (৳{initial_payment:,.2f}) cannot exceed total purchase value (৳{total_amount_bdt:,.2f}).")

    outstanding_bdt = (total_amount_bdt - initial_payment).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if outstanding_bdt == Decimal("0.00"):
        payment_status = "FULLY_PAID"
    elif initial_payment > Decimal("0.00"):
        payment_status = "PARTIALLY_PAID"
    else:
        payment_status = "UNPAID"

    tx_num = generate_transaction_number(db, "PURCHASE", tx_date)

    tx = Transaction(
        transaction_number=tx_num,
        transaction_type="PURCHASE",
        customer_id=customer.id,
        currency_code="MYR",
        myr_quantity=myr_quantity,
        exchange_rate=purchase_rate,
        total_amount_bdt=total_amount_bdt,
        paid_amount_bdt=initial_payment,
        outstanding_amount_bdt=outstanding_bdt,
        cogs_bdt=Decimal("0.00"),
        payment_status=payment_status,
        status="POSTED",
        payment_method=payment_method if initial_payment > Decimal("0") else None,
        notes=notes,
        created_by_id=created_by_id,
        transaction_date=tx_date,
    )
    db.add(tx)
    db.flush()

    # 1. Inflow into Inventory & update Moving WAC
    inv, movement = record_purchase_inflow(
        db=db,
        quantity=myr_quantity,
        rate=purchase_rate,
        transaction_id=tx.id,
        currency_code="MYR",
    )

    # 2. Update Customer Accounts Payable balance
    if outstanding_bdt > Decimal("0.00"):
        customer.total_payable_bdt = (customer.total_payable_bdt + outstanding_bdt).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # 3. Deduct cash outflow for initial payment and create Payment record
    if initial_payment > Decimal("0.00"):
        record_cash_outflow(
            db=db,
            cash_account_id=cash_acc.id,
            amount=initial_payment,
            reference_type="PURCHASE",
            reference_id=tx.id,
            notes=f"Initial payment for {tx.transaction_number}",
        )
        pay_num = generate_payment_number(db, tx_date)
        payment_record = Payment(
            payment_number=pay_num,
            payment_type="OUTGOING",
            customer_id=customer.id,
            transaction_id=tx.id,
            amount_bdt=initial_payment,
            cash_account_id=cash_acc.id,
            payment_method=payment_method,
            reference_note=f"Initial downpayment for {tx.transaction_number}",
            created_by_id=created_by_id,
            payment_date=tx_date,
        )
        db.add(payment_record)

    # 4. Post Double-Entry Journal Entry
    # DEBIT: 1040 MYR Currency Inventory (total_amount_bdt)
    # CREDIT: Cash Account GL (initial_payment) if initial_payment > 0
    # CREDIT: 2010 Accounts Payable (outstanding_bdt) if outstanding_bdt > 0
    cash_gl = db.query(ChartOfAccount).filter_by(id=cash_acc.gl_account_id).first()
    lines = [
        ("1040", total_amount_bdt, Decimal("0.00"), f"Purchase {myr_quantity:,.2f} MYR @ ৳{purchase_rate:,.4f}"),
    ]
    if initial_payment > Decimal("0.00"):
        lines.append(
            (cash_gl.account_code, Decimal("0.00"), initial_payment, f"Cash paid on purchase {tx.transaction_number}")
        )
    if outstanding_bdt > Decimal("0.00"):
        lines.append(
            ("2010", Decimal("0.00"), outstanding_bdt, f"Accounts Payable to {customer.full_name} for {tx.transaction_number}")
        )

    post_journal_entry(
        db=db,
        entry_date=tx_date.date(),
        reference_type="PURCHASE",
        reference_id=tx.id,
        description=f"MYR Purchase {tx.transaction_number} from {customer.full_name} ({myr_quantity:,.2f} MYR @ ৳{purchase_rate:,.4f})",
        lines=lines,
        user_id=created_by_id,
    )

    # 5. Audit Log
    audit = AuditLog(
        user_id=created_by_id,
        action="CREATE_PURCHASE",
        entity_name="Transaction",
        entity_id=tx.id,
        new_values={
            "tx_num": tx.transaction_number,
            "customer": customer.full_name,
            "quantity": str(myr_quantity),
            "rate": str(purchase_rate),
            "total_bdt": str(total_amount_bdt),
            "paid_bdt": str(initial_payment),
            "outstanding_bdt": str(outstanding_bdt),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(tx)
    return tx


def create_sales_transaction(
    db: Session,
    customer_id: str,
    myr_quantity: Decimal,
    selling_rate: Decimal,
    initial_payment: Decimal,
    cash_account_id: str,
    payment_method: str,
    created_by_id: str,
    transaction_date: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Transaction:
    if myr_quantity <= Decimal("0"):
        raise ValueError("MYR Quantity must be positive.")
    if selling_rate <= Decimal("0"):
        raise ValueError("Selling Rate must be positive.")

    customer = db.query(Customer).filter_by(id=customer_id).with_for_update().first()
    if not customer:
        raise ValueError("Customer not found.")
    if customer.is_archived:
        raise ValueError("Cannot perform transactions for an archived customer.")

    cash_acc = db.query(CashAccount).filter_by(id=cash_account_id).first()
    if not cash_acc:
        raise ValueError("Invalid Cash/Bank account selected.")

    tx_date = transaction_date or get_utc_now()
    total_amount_bdt = (myr_quantity * selling_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    initial_payment = initial_payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if initial_payment < Decimal("0"):
        raise ValueError("Payment amount cannot be negative.")
    if initial_payment > total_amount_bdt:
        raise ValueError(f"Initial payment (৳{initial_payment:,.2f}) cannot exceed total sale value (৳{total_amount_bdt:,.2f}).")

    outstanding_bdt = (total_amount_bdt - initial_payment).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if outstanding_bdt == Decimal("0.00"):
        payment_status = "FULLY_PAID"
    elif initial_payment > Decimal("0.00"):
        payment_status = "PARTIALLY_PAID"
    else:
        payment_status = "UNPAID"

    tx_num = generate_transaction_number(db, "SALE", tx_date)

    # 1. Deduct Inventory & calculate COGS using moving WAC (Raises ValueError if insufficient inventory!)
    inv, movement, cogs = record_sales_outflow(
        db=db,
        quantity=myr_quantity,
        transaction_id=None,  # updated right below
        currency_code="MYR",
    )

    tx = Transaction(
        transaction_number=tx_num,
        transaction_type="SALE",
        customer_id=customer.id,
        currency_code="MYR",
        myr_quantity=myr_quantity,
        exchange_rate=selling_rate,
        total_amount_bdt=total_amount_bdt,
        paid_amount_bdt=initial_payment,
        outstanding_amount_bdt=outstanding_bdt,
        cogs_bdt=cogs,
        payment_status=payment_status,
        status="POSTED",
        payment_method=payment_method if initial_payment > Decimal("0") else None,
        notes=notes,
        created_by_id=created_by_id,
        transaction_date=tx_date,
    )
    db.add(tx)
    db.flush()
    movement.transaction_id = tx.id

    # 2. Update Customer Accounts Receivable balance
    if outstanding_bdt > Decimal("0.00"):
        customer.total_receivable_bdt = (customer.total_receivable_bdt + outstanding_bdt).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # 3. Add cash inflow for initial payment and create Payment record
    if initial_payment > Decimal("0.00"):
        record_cash_inflow(
            db=db,
            cash_account_id=cash_acc.id,
            amount=initial_payment,
            reference_type="SALE",
            reference_id=tx.id,
            notes=f"Initial payment for {tx.transaction_number}",
        )
        pay_num = generate_payment_number(db, tx_date)
        payment_record = Payment(
            payment_number=pay_num,
            payment_type="INCOMING",
            customer_id=customer.id,
            transaction_id=tx.id,
            amount_bdt=initial_payment,
            cash_account_id=cash_acc.id,
            payment_method=payment_method,
            reference_note=f"Initial payment for {tx.transaction_number}",
            created_by_id=created_by_id,
            payment_date=tx_date,
        )
        db.add(payment_record)

    # 4. Post Double-Entry Compound Journal Entry
    # DEBIT: Cash Account GL (initial_payment) if initial_payment > 0
    # DEBIT: 1030 Accounts Receivable (outstanding_bdt) if outstanding_bdt > 0
    # CREDIT: 4010 MYR Sales Revenue (total_amount_bdt)
    # DEBIT: 5010 Cost of Goods Sold (cogs)
    # CREDIT: 1040 MYR Currency Inventory (cogs)
    cash_gl = db.query(ChartOfAccount).filter_by(id=cash_acc.gl_account_id).first()
    lines = []
    if initial_payment > Decimal("0.00"):
        lines.append(
            (cash_gl.account_code, initial_payment, Decimal("0.00"), f"Cash received for sale {tx.transaction_number}")
        )
    if outstanding_bdt > Decimal("0.00"):
        lines.append(
            ("1030", outstanding_bdt, Decimal("0.00"), f"Accounts Receivable from {customer.full_name} for {tx.transaction_number}")
        )
    lines.append(
        ("4010", Decimal("0.00"), total_amount_bdt, f"Sale of {myr_quantity:,.2f} MYR @ ৳{selling_rate:,.4f}")
    )
    # COGS and Inventory lines
    lines.append(
        ("5010", cogs, Decimal("0.00"), f"Cost of {myr_quantity:,.2f} MYR sold ({tx.transaction_number})")
    )
    lines.append(
        ("1040", Decimal("0.00"), cogs, f"Inventory reduction for sale {tx.transaction_number}")
    )

    post_journal_entry(
        db=db,
        entry_date=tx_date.date(),
        reference_type="SALE",
        reference_id=tx.id,
        description=f"MYR Sale {tx.transaction_number} to {customer.full_name} ({myr_quantity:,.2f} MYR @ ৳{selling_rate:,.4f})",
        lines=lines,
        user_id=created_by_id,
    )

    # 5. Audit Log
    audit = AuditLog(
        user_id=created_by_id,
        action="CREATE_SALE",
        entity_name="Transaction",
        entity_id=tx.id,
        new_values={
            "tx_num": tx.transaction_number,
            "customer": customer.full_name,
            "quantity": str(myr_quantity),
            "rate": str(selling_rate),
            "total_bdt": str(total_amount_bdt),
            "paid_bdt": str(initial_payment),
            "outstanding_bdt": str(outstanding_bdt),
            "cogs_bdt": str(cogs),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(tx)
    return tx


def void_cancel_transaction(
    db: Session,
    transaction_id: str,
    reason: str,
    user_id: str,
) -> Transaction:
    from app.models import JournalEntry

    tx = db.query(Transaction).filter_by(id=transaction_id).with_for_update().first()
    if not tx:
        raise ValueError("Transaction not found.")
    if tx.status == "CANCELLED":
        raise ValueError("Transaction has already been cancelled.")

    # Check if there are subsequent installment payments on this transaction
    subsequent_payments = (
        db.query(Payment)
        .filter(Payment.transaction_id == tx.id, Payment.amount_bdt > 0)
        .all()
    )
    # If there are payments beyond the initial one, we cannot simply void the transaction without reversing those payments first!
    if len(subsequent_payments) > (1 if tx.paid_amount_bdt > 0 else 0):
        raise ValueError("Cannot void transaction with subsequent installment payments recorded. Please reverse individual payments first.")

    customer = db.query(Customer).filter_by(id=tx.customer_id).with_for_update().first()
    now_date = datetime.now(timezone.utc).date()

    if tx.transaction_type == "PURCHASE":
        # 1. Reverse Inventory: Must deduct MYR from inventory
        record_reversal_adjustment(
            db=db,
            quantity_delta=-tx.myr_quantity,
            unit_cost=tx.exchange_rate,
            total_cost=tx.total_amount_bdt,
            reversal_type="REVERSAL_OUTFLOW",
            transaction_id=tx.id,
            currency_code="MYR",
        )
        # 2. Reverse Customer Accounts Payable
        if tx.outstanding_amount_bdt > Decimal("0.00"):
            customer.total_payable_bdt = max(Decimal("0.00"), customer.total_payable_bdt - tx.outstanding_amount_bdt)

        # 3. Reverse initial cash paid
        if tx.paid_amount_bdt > Decimal("0.00"):
            # Cash was paid out, so cancellation returns cash to company drawer
            default_cash = db.query(CashAccount).filter_by(account_type="CASH").first()
            record_cash_inflow(
                db=db,
                cash_account_id=default_cash.id,
                amount=tx.paid_amount_bdt,
                reference_type="REVERSAL",
                reference_id=tx.id,
                notes=f"Reversal refund of purchase {tx.transaction_number}",
            )

    elif tx.transaction_type == "SALE":
        # 1. Reverse Inventory: Return MYR to inventory at original COGS unit cost
        record_reversal_adjustment(
            db=db,
            quantity_delta=tx.myr_quantity,
            unit_cost=tx.cogs_bdt / tx.myr_quantity if tx.myr_quantity > 0 else Decimal("0"),
            total_cost=tx.cogs_bdt,
            reversal_type="REVERSAL_INFLOW",
            transaction_id=tx.id,
            currency_code="MYR",
        )
        # 2. Reverse Customer Accounts Receivable
        if tx.outstanding_amount_bdt > Decimal("0.00"):
            customer.total_receivable_bdt = max(Decimal("0.00"), customer.total_receivable_bdt - tx.outstanding_amount_bdt)

        # 3. Reverse initial cash received
        if tx.paid_amount_bdt > Decimal("0.00"):
            # Cash was collected, so cancellation refunds cash to customer
            default_cash = db.query(CashAccount).filter_by(account_type="CASH").first()
            record_cash_outflow(
                db=db,
                cash_account_id=default_cash.id,
                amount=tx.paid_amount_bdt,
                reference_type="REVERSAL",
                reference_id=tx.id,
                notes=f"Reversal refund of sale {tx.transaction_number}",
            )

    # 4. Find and reverse the associated Journal Entry
    original_je = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference_type == tx.transaction_type, JournalEntry.reference_id == tx.id)
        .first()
    )
    if original_je and not original_je.is_reversed:
        reverse_journal_entry(
            db=db,
            original_entry_id=original_je.id,
            reversal_date=now_date,
            reason=reason,
            user_id=user_id,
        )

    tx.status = "CANCELLED"

    audit = AuditLog(
        user_id=user_id,
        action="CANCEL_TRANSACTION",
        entity_name="Transaction",
        entity_id=tx.id,
        new_values={"status": "CANCELLED", "reason": reason},
    )
    db.add(audit)
    db.commit()
    db.refresh(tx)
    return tx
