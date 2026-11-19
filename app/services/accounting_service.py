from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timezone
from typing import List, Tuple, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from app.models import (
    ChartOfAccount,
    JournalEntry,
    JournalEntryLine,
    AuditLog,
    Transaction,
    Payment,
    Expense,
)


def get_account_by_code(db: Session, code: str) -> ChartOfAccount:
    account = db.query(ChartOfAccount).filter_by(account_code=code, is_active=True).first()
    if not account:
        raise ValueError(f"Chart of Account code '{code}' does not exist or is inactive!")
    return account


def generate_entry_number(db: Session, entry_date: date) -> str:
    prefix = f"JE-{entry_date.strftime('%Y%m%d')}"
    count = db.query(JournalEntry).filter(JournalEntry.entry_number.like(f"{prefix}%")).count()
    return f"{prefix}-{(count + 1):04d}"


def post_journal_entry(
    db: Session,
    entry_date: date,
    reference_type: str,
    reference_id: Optional[str],
    description: str,
    lines: List[Tuple[str, Decimal, Decimal, Optional[str]]],
    user_id: str,
) -> JournalEntry:
    """
    Creates a double-entry balanced journal entry.
    Each item in lines: (account_code, debit_amount, credit_amount, line_description)
    """
    if not lines:
        raise ValueError("Cannot post empty journal entry.")

    total_debits = Decimal("0.00")
    total_credits = Decimal("0.00")

    entry_lines_to_add = []

    for item in lines:
        code, debit, credit, line_desc = item
        debit = Decimal(str(debit)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        credit = Decimal(str(credit)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if debit < Decimal("0") or credit < Decimal("0"):
            raise ValueError(f"Debit or Credit amount cannot be negative for account {code}.")
        if debit > Decimal("0") and credit > Decimal("0"):
            raise ValueError(f"A single line cannot have both debit and credit amounts for account {code}.")
        if debit == Decimal("0") and credit == Decimal("0"):
            continue

        account = get_account_by_code(db, code)
        total_debits += debit
        total_credits += credit

        entry_lines_to_add.append((account.id, debit, credit, line_desc))

    # Validate double-entry balance: Debits must equal Credits
    if total_debits != total_credits:
        raise ValueError(
            f"Unbalanced Journal Entry! Total Debits: ৳{total_debits:,.2f} != Total Credits: ৳{total_credits:,.2f}"
        )

    entry_number = generate_entry_number(db, entry_date)
    # Ensure uniqueness
    while db.query(JournalEntry).filter_by(entry_number=entry_number).first():
        num = int(entry_number.split("-")[-1]) + 1
        entry_number = f"JE-{entry_date.strftime('%Y%m%d')}-{num:04d}"

    journal_entry = JournalEntry(
        entry_number=entry_number,
        entry_date=entry_date,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        is_reversed=False,
        created_by_id=user_id,
    )
    db.add(journal_entry)
    db.flush()

    for acc_id, deb, cred, l_desc in entry_lines_to_add:
        line = JournalEntryLine(
            journal_entry_id=journal_entry.id,
            account_id=acc_id,
            debit_amount=deb,
            credit_amount=cred,
            line_description=l_desc or description,
        )
        db.add(line)

    db.flush()
    return journal_entry


def reverse_journal_entry(
    db: Session,
    original_entry_id: str,
    reversal_date: date,
    reason: str,
    user_id: str,
) -> JournalEntry:
    original = db.query(JournalEntry).filter_by(id=original_entry_id).first()
    if not original:
        raise ValueError("Original journal entry not found.")
    if original.is_reversed:
        raise ValueError("Journal entry has already been reversed.")

    # Build mirrored counter lines: swap debits and credits
    counter_lines = []
    for line in original.lines:
        account = db.query(ChartOfAccount).filter_by(id=line.account_id).first()
        counter_lines.append(
            (
                account.account_code,
                line.credit_amount,  # Swapped
                line.debit_amount,   # Swapped
                f"Reversal: {line.line_description or ''}",
            )
        )

    reversal_entry = post_journal_entry(
        db=db,
        entry_date=reversal_date,
        reference_type="REVERSAL",
        reference_id=original.id,
        description=f"Reversal of {original.entry_number}. Reason: {reason}",
        lines=counter_lines,
        user_id=user_id,
    )

    original.is_reversed = True
    original.reversed_by_entry_id = reversal_entry.id
    db.flush()
    return reversal_entry


def get_trial_balance(db: Session, as_of_date: Optional[date] = None) -> dict:
    query = (
        db.query(
            ChartOfAccount.id,
            ChartOfAccount.account_code,
            ChartOfAccount.account_name,
            ChartOfAccount.account_type,
            ChartOfAccount.normal_balance,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), Decimal("0.00")).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), Decimal("0.00")).label("total_credit"),
        )
        .join(JournalEntryLine, ChartOfAccount.id == JournalEntryLine.account_id)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
    )

    if as_of_date:
        query = query.filter(JournalEntry.entry_date <= as_of_date)

    results = query.group_by(
        ChartOfAccount.id,
        ChartOfAccount.account_code,
        ChartOfAccount.account_name,
        ChartOfAccount.account_type,
        ChartOfAccount.normal_balance,
    ).order_by(ChartOfAccount.account_code).all()

    accounts = []
    sum_debits = Decimal("0.00")
    sum_credits = Decimal("0.00")

    for r in results:
        t_deb = Decimal(str(r.total_debit))
        t_cred = Decimal(str(r.total_credit))

        # Net balance based on normal balance
        if r.normal_balance == "DEBIT":
            net_balance = t_deb - t_cred
            disp_debit = net_balance if net_balance > 0 else Decimal("0.00")
            disp_credit = -net_balance if net_balance < 0 else Decimal("0.00")
        else:
            net_balance = t_cred - t_deb
            disp_credit = net_balance if net_balance > 0 else Decimal("0.00")
            disp_debit = -net_balance if net_balance < 0 else Decimal("0.00")

        sum_debits += disp_debit
        sum_credits += disp_credit

        accounts.append({
            "account_code": r.account_code,
            "account_name": r.account_name,
            "account_type": r.account_type,
            "normal_balance": r.normal_balance,
            "debit": disp_debit,
            "credit": disp_credit,
        })

    is_balanced = (sum_debits == sum_credits)
    return {
        "as_of_date": as_of_date or date.today(),
        "accounts": accounts,
        "total_debits": sum_debits,
        "total_credits": sum_credits,
        "is_balanced": is_balanced,
    }


def get_profit_and_loss(db: Session, from_date: Optional[date] = None, to_date: Optional[date] = None) -> dict:
    query = (
        db.query(
            ChartOfAccount.account_code,
            ChartOfAccount.account_name,
            ChartOfAccount.account_type,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), Decimal("0.00")).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), Decimal("0.00")).label("total_credit"),
        )
        .join(JournalEntryLine, ChartOfAccount.id == JournalEntryLine.account_id)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .filter(ChartOfAccount.account_type.in_(["INCOME", "EXPENSE"]))
    )

    if from_date:
        query = query.filter(JournalEntry.entry_date >= from_date)
    if to_date:
        query = query.filter(JournalEntry.entry_date <= to_date)

    rows = query.group_by(
        ChartOfAccount.account_code,
        ChartOfAccount.account_name,
        ChartOfAccount.account_type,
    ).all()

    income_items = []
    cogs_items = []
    expense_items = []

    total_revenue = Decimal("0.00")
    total_cogs = Decimal("0.00")
    total_operating_expenses = Decimal("0.00")

    for r in rows:
        deb = Decimal(str(r.total_debit))
        cred = Decimal(str(r.total_credit))

        if r.account_type == "INCOME":
            net_income = cred - deb
            if net_income != Decimal("0.00"):
                income_items.append({"code": r.account_code, "name": r.account_name, "amount": net_income})
                total_revenue += net_income
        elif r.account_type == "EXPENSE":
            net_expense = deb - cred
            if r.account_code == "5010":  # Cost of Goods Sold
                cogs_items.append({"code": r.account_code, "name": r.account_name, "amount": net_expense})
                total_cogs += net_expense
            else:
                if net_expense != Decimal("0.00"):
                    expense_items.append({"code": r.account_code, "name": r.account_name, "amount": net_expense})
                    total_operating_expenses += net_expense

    gross_profit = total_revenue - total_cogs
    net_profit = gross_profit - total_operating_expenses

    return {
        "from_date": from_date,
        "to_date": to_date or date.today(),
        "income_items": income_items,
        "total_revenue": total_revenue,
        "cogs_items": cogs_items,
        "total_cogs": total_cogs,
        "gross_profit": gross_profit,
        "expense_items": expense_items,
        "total_operating_expenses": total_operating_expenses,
        "net_profit": net_profit,
    }


def get_balance_sheet(db: Session, as_of_date: Optional[date] = None) -> dict:
    as_of = as_of_date or date.today()

    query = (
        db.query(
            ChartOfAccount.account_code,
            ChartOfAccount.account_name,
            ChartOfAccount.account_type,
            ChartOfAccount.normal_balance,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), Decimal("0.00")).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), Decimal("0.00")).label("total_credit"),
        )
        .join(JournalEntryLine, ChartOfAccount.id == JournalEntryLine.account_id)
        .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
        .filter(JournalEntry.entry_date <= as_of)
        .filter(ChartOfAccount.account_type.in_(["ASSET", "LIABILITY", "EQUITY"]))
        .group_by(
            ChartOfAccount.account_code,
            ChartOfAccount.account_name,
            ChartOfAccount.account_type,
            ChartOfAccount.normal_balance,
        )
    )

    rows = query.all()

    assets = []
    liabilities = []
    equity = []

    total_assets = Decimal("0.00")
    total_liabilities = Decimal("0.00")
    total_equity_base = Decimal("0.00")

    for r in rows:
        deb = Decimal(str(r.total_debit))
        cred = Decimal(str(r.total_credit))

        if r.account_type == "ASSET":
            val = deb - cred
            if val != Decimal("0.00"):
                assets.append({"code": r.account_code, "name": r.account_name, "amount": val})
                total_assets += val
        elif r.account_type == "LIABILITY":
            val = cred - deb
            if val != Decimal("0.00"):
                liabilities.append({"code": r.account_code, "name": r.account_name, "amount": val})
                total_liabilities += val
        elif r.account_type == "EQUITY":
            val = cred - deb
            if val != Decimal("0.00"):
                equity.append({"code": r.account_code, "name": r.account_name, "amount": val})
                total_equity_base += val

    # Current Period Earnings calculation to date:
    pnl = get_profit_and_loss(db, from_date=None, to_date=as_of)
    current_period_earnings = pnl["net_profit"]

    # Add Current Period Earnings to equity
    equity.append({
        "code": "3030",
        "name": "Current Period Net Earnings (P&L)",
        "amount": current_period_earnings,
    })
    total_equity = total_equity_base + current_period_earnings

    total_liabilities_and_equity = total_liabilities + total_equity
    difference = total_assets - total_liabilities_and_equity
    is_balanced = (difference == Decimal("0.00"))

    return {
        "as_of_date": as_of,
        "assets": assets,
        "total_assets": total_assets,
        "liabilities": liabilities,
        "total_liabilities": total_liabilities,
        "equity": equity,
        "total_equity": total_equity,
        "total_liabilities_and_equity": total_liabilities_and_equity,
        "difference": difference,
        "is_balanced": is_balanced,
    }


def get_cash_flow_statement(db: Session, from_date: Optional[date] = None, to_date: Optional[date] = None) -> dict:
    from app.models import CashMovement, CashAccount

    query = db.query(CashMovement).join(CashAccount, CashMovement.cash_account_id == CashAccount.id)
    if from_date:
        query = query.filter(CashMovement.created_at >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc))
    if to_date:
        query = query.filter(CashMovement.created_at <= datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc))

    movements = query.all()

    inflows = sum((m.amount for m in movements if m.movement_type == "INFLOW"), Decimal("0.00"))
    outflows = sum((m.amount for m in movements if m.movement_type == "OUTFLOW"), Decimal("0.00"))
    net_cash_flow = inflows - outflows

    # Total current cash across all cash accounts
    total_cash_now = sum((ca.current_balance for ca in db.query(CashAccount).all()), Decimal("0.00"))

    return {
        "from_date": from_date,
        "to_date": to_date or date.today(),
        "total_inflows": inflows,
        "total_outflows": outflows,
        "net_cash_flow": net_cash_flow,
        "current_total_cash": total_cash_now,
    }
