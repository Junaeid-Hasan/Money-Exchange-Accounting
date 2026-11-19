from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import Expense, ExpenseCategory, CashAccount, ChartOfAccount, AuditLog
from app.services.cash_service import record_cash_outflow, record_cash_inflow
from app.services.accounting_service import post_journal_entry, reverse_journal_entry


def generate_expense_number(db: Session, exp_date: date) -> str:
    prefix = f"EXP-{exp_date.strftime('%Y%m%d')}"
    count = db.query(Expense).filter(Expense.expense_number.like(f"{prefix}%")).count()
    return f"{prefix}-{(count + 1):04d}"


def create_expense(
    db: Session,
    category_id: str,
    amount_bdt: Decimal,
    cash_account_id: str,
    expense_date: date,
    description: str,
    created_by_id: str,
    receipt_file_url: Optional[str] = None,
) -> Expense:
    amount_bdt = amount_bdt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount_bdt <= Decimal("0.00"):
        raise ValueError("Expense amount must be positive.")

    category = db.query(ExpenseCategory).filter_by(id=category_id).first()
    if not category:
        raise ValueError("Expense category not found.")

    cash_acc = db.query(CashAccount).filter_by(id=cash_account_id).first()
    if not cash_acc:
        raise ValueError("Cash account not found.")

    exp_num = generate_expense_number(db, expense_date)

    expense = Expense(
        expense_number=exp_num,
        category_id=category.id,
        amount_bdt=amount_bdt,
        cash_account_id=cash_acc.id,
        expense_date=expense_date,
        description=description,
        receipt_file_url=receipt_file_url,
        status="POSTED",
        created_by_id=created_by_id,
    )
    db.add(expense)
    db.flush()

    # Cash Outflow
    record_cash_outflow(
        db=db,
        cash_account_id=cash_acc.id,
        amount=amount_bdt,
        reference_type="EXPENSE",
        reference_id=expense.id,
        notes=f"Expense {expense.expense_number} ({category.name})",
    )

    # Post Double-Entry Journal Entry
    # DEBIT: category.gl_account.account_code (amount_bdt)
    # CREDIT: cash_acc.gl_account.account_code (amount_bdt)
    category_gl = db.query(ChartOfAccount).filter_by(id=category.gl_account_id).first()
    cash_gl = db.query(ChartOfAccount).filter_by(id=cash_acc.gl_account_id).first()

    lines = [
        (category_gl.account_code, amount_bdt, Decimal("0.00"), f"Expense: {description}"),
        (cash_gl.account_code, Decimal("0.00"), amount_bdt, f"Payment for {expense.expense_number}"),
    ]

    post_journal_entry(
        db=db,
        entry_date=expense_date,
        reference_type="EXPENSE",
        reference_id=expense.id,
        description=f"Operating Expense {expense.expense_number}: {category.name} ({description})",
        lines=lines,
        user_id=created_by_id,
    )

    audit = AuditLog(
        user_id=created_by_id,
        action="CREATE_EXPENSE",
        entity_name="Expense",
        entity_id=expense.id,
        new_values={
            "expense_number": expense.expense_number,
            "category": category.name,
            "amount": str(amount_bdt),
            "date": str(expense_date),
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(expense)
    return expense


def void_expense(db: Session, expense_id: str, reason: str, user_id: str) -> Expense:
    from app.models import JournalEntry

    expense = db.query(Expense).filter_by(id=expense_id).with_for_update().first()
    if not expense:
        raise ValueError("Expense not found.")
    if expense.status == "VOIDED":
        raise ValueError("Expense is already voided.")

    # 1. Reverse Cash Outflow (return cash)
    record_cash_inflow(
        db=db,
        cash_account_id=expense.cash_account_id,
        amount=expense.amount_bdt,
        reference_type="REVERSAL",
        reference_id=expense.id,
        notes=f"Refund from voided expense {expense.expense_number}",
    )

    # 2. Reverse Journal Entry
    je = (
        db.query(JournalEntry)
        .filter(JournalEntry.reference_type == "EXPENSE", JournalEntry.reference_id == expense.id)
        .first()
    )
    if je and not je.is_reversed:
        reverse_journal_entry(
            db=db,
            original_entry_id=je.id,
            reversal_date=datetime.now(timezone.utc).date(),
            reason=reason,
            user_id=user_id,
        )

    expense.status = "VOIDED"

    audit = AuditLog(
        user_id=user_id,
        action="VOID_EXPENSE",
        entity_name="Expense",
        entity_id=expense.id,
        new_values={"status": "VOIDED", "reason": reason},
    )
    db.add(audit)
    db.commit()
    db.refresh(expense)
    return expense
