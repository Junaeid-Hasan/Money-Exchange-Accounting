from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from app.models import (
    CashAccount,
    CashMovement,
    DailyCashReconciliation,
    ChartOfAccount,
    AuditLog,
)
from app.services.accounting_service import post_journal_entry


def get_default_cash_account(db: Session, account_type: str = "CASH") -> CashAccount:
    acc = db.query(CashAccount).filter_by(account_type=account_type).first()
    if not acc:
        acc = db.query(CashAccount).first()
    if not acc:
        raise ValueError("No cash accounts configured in the system!")
    return acc


def record_cash_inflow(
    db: Session,
    cash_account_id: str,
    amount: Decimal,
    reference_type: str,
    reference_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> CashMovement:
    if amount <= Decimal("0.00"):
        raise ValueError("Inflow amount must be positive.")

    cash_acc = db.query(CashAccount).filter_by(id=cash_account_id).with_for_update().first()
    if not cash_acc:
        raise ValueError("Cash account not found.")

    new_balance = (cash_acc.current_balance + amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cash_acc.current_balance = new_balance

    movement = CashMovement(
        cash_account_id=cash_acc.id,
        movement_type="INFLOW",
        amount=amount,
        balance_after=new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )
    db.add(movement)
    db.flush()
    return movement


def record_cash_outflow(
    db: Session,
    cash_account_id: str,
    amount: Decimal,
    reference_type: str,
    reference_id: Optional[str] = None,
    notes: Optional[str] = None,
    allow_negative: bool = False,
) -> CashMovement:
    if amount <= Decimal("0.00"):
        raise ValueError("Outflow amount must be positive.")

    cash_acc = db.query(CashAccount).filter_by(id=cash_account_id).with_for_update().first()
    if not cash_acc:
        raise ValueError("Cash account not found.")

    if not allow_negative and cash_acc.current_balance < amount:
        # Warning/alert or prevention depending on policy
        pass

    new_balance = (cash_acc.current_balance - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cash_acc.current_balance = new_balance

    movement = CashMovement(
        cash_account_id=cash_acc.id,
        movement_type="OUTFLOW",
        amount=amount,
        balance_after=new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )
    db.add(movement)
    db.flush()
    return movement


def transfer_cash_funds(
    db: Session,
    from_account_id: str,
    to_account_id: str,
    amount: Decimal,
    user_id: str,
    transfer_date: date,
    notes: Optional[str] = None,
) -> Tuple[CashMovement, CashMovement]:
    if amount <= Decimal("0"):
        raise ValueError("Transfer amount must be positive.")
    if from_account_id == to_account_id:
        raise ValueError("Source and destination accounts must be different.")

    from_acc = db.query(CashAccount).filter_by(id=from_account_id).first()
    to_acc = db.query(CashAccount).filter_by(id=to_account_id).first()
    if not from_acc or not to_acc:
        raise ValueError("Invalid source or destination cash account.")

    # 1. Outflow from source
    outflow = record_cash_outflow(
        db, from_acc.id, amount, reference_type="TRANSFER", notes=f"Transfer to {to_acc.account_name}. {notes or ''}"
    )
    # 2. Inflow to destination
    inflow = record_cash_inflow(
        db, to_acc.id, amount, reference_type="TRANSFER", notes=f"Transfer from {from_acc.account_name}. {notes or ''}"
    )

    # 3. Post Contra Journal Entry
    # Debit: Destination Cash GL, Credit: Source Cash GL
    from_gl = db.query(ChartOfAccount).filter_by(id=from_acc.gl_account_id).first()
    to_gl = db.query(ChartOfAccount).filter_by(id=to_acc.gl_account_id).first()

    lines = [
        (to_gl.account_code, amount, Decimal("0.00"), f"Fund transfer into {to_acc.account_name}"),
        (from_gl.account_code, Decimal("0.00"), amount, f"Fund transfer out of {from_acc.account_name}"),
    ]

    post_journal_entry(
        db=db,
        entry_date=transfer_date,
        reference_type="TRANSFER",
        reference_id=outflow.id,
        description=f"Contra fund transfer from {from_acc.account_name} to {to_acc.account_name}",
        lines=lines,
        user_id=user_id,
    )

    db.commit()
    return outflow, inflow


def reconcile_daily_cash(
    db: Session,
    cash_account_id: str,
    reconciliation_date: date,
    physical_balance: Decimal,
    user_id: str,
    notes: Optional[str] = None,
) -> DailyCashReconciliation:
    cash_acc = db.query(CashAccount).filter_by(id=cash_account_id).with_for_update().first()
    if not cash_acc:
        raise ValueError("Cash account not found.")

    system_balance = cash_acc.current_balance
    discrepancy = (physical_balance - system_balance).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Check if existing reconciliation for today
    existing = (
        db.query(DailyCashReconciliation)
        .filter_by(cash_account_id=cash_account_id, reconciliation_date=reconciliation_date)
        .first()
    )

    if existing:
        recon = existing
        recon.system_balance = system_balance
        recon.physical_balance = physical_balance
        recon.discrepancy = discrepancy
        recon.notes = notes
        recon.reconciled_by_id = user_id
    else:
        recon = DailyCashReconciliation(
            cash_account_id=cash_account_id,
            reconciliation_date=reconciliation_date,
            system_balance=system_balance,
            physical_balance=physical_balance,
            discrepancy=discrepancy,
            status="BALANCED" if discrepancy == Decimal("0.00") else "DISCREPANCY_RECORDED",
            notes=notes,
            reconciled_by_id=user_id,
        )
        db.add(recon)

    # If discrepancy exists, post adjustment to align ledger with physical reality
    if discrepancy != Decimal("0.00"):
        gl_acc = db.query(ChartOfAccount).filter_by(id=cash_acc.gl_account_id).first()
        if discrepancy < Decimal("0.00"):
            # Cash Shortage: Debit Expense (6080), Credit Cash GL
            shortage_amt = abs(discrepancy)
            lines = [
                ("6080", shortage_amt, Decimal("0.00"), f"Cash Shortage reconciliation on {reconciliation_date}"),
                (gl_acc.account_code, Decimal("0.00"), shortage_amt, f"Adjustment for cash shortage"),
            ]
            record_cash_outflow(
                db, cash_acc.id, shortage_amt, reference_type="RECONCILIATION", reference_id=recon.id, notes="Shortage adjustment"
            )
        else:
            # Cash Overplus: Debit Cash GL, Credit Other Income (4030)
            overplus_amt = discrepancy
            lines = [
                (gl_acc.account_code, overplus_amt, Decimal("0.00"), f"Adjustment for cash overplus"),
                ("4030", Decimal("0.00"), overplus_amt, f"Cash Overplus reconciliation on {reconciliation_date}"),
            ]
            record_cash_inflow(
                db, cash_acc.id, overplus_amt, reference_type="RECONCILIATION", reference_id=recon.id, notes="Overplus adjustment"
            )

        post_journal_entry(
            db=db,
            entry_date=reconciliation_date,
            reference_type="ADJUSTMENT",
            reference_id=recon.id,
            description=f"Daily cash reconciliation adjustment for {cash_acc.account_name}. Variance: ৳{discrepancy:,.2f}",
            lines=lines,
            user_id=user_id,
        )

    db.commit()
    db.refresh(recon)
    return recon
