from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from app.models import (
    Transaction,
    Customer,
    CurrencyInventory,
    CashAccount,
    Payment,
    Expense,
    ExpenseCategory,
    JournalEntry,
    JournalEntryLine,
    ChartOfAccount,
)
from app.services.accounting_service import get_profit_and_loss, get_balance_sheet, get_cash_flow_statement


def get_dashboard_summary(db: Session) -> dict:
    today = date.today()
    first_of_month = today.replace(day=1)
    first_of_year = today.replace(month=1, day=1)

    # 1. Today's P&L
    today_pnl = get_profit_and_loss(db, from_date=today, to_date=today)
    today_gross_profit = today_pnl["gross_profit"]
    today_net_profit = today_pnl["net_profit"]

    # 2. Month-to-date P&L
    month_pnl = get_profit_and_loss(db, from_date=first_of_month, to_date=today)
    month_gross_profit = month_pnl["gross_profit"]
    month_net_profit = month_pnl["net_profit"]

    # 3. Year-to-date P&L
    year_pnl = get_profit_and_loss(db, from_date=first_of_year, to_date=today)
    year_net_profit = year_pnl["net_profit"]
    year_operating_expenses = year_pnl["total_operating_expenses"]

    # 4. Inventory stats
    myr_inv = db.query(CurrencyInventory).filter_by(currency_code="MYR").first()
    current_myr_qty = myr_inv.total_quantity if myr_inv else Decimal("0.0000")
    current_myr_val = myr_inv.total_valuation_bdt if myr_inv else Decimal("0.00")
    current_myr_wac = myr_inv.weighted_average_cost if myr_inv else Decimal("0.0000")

    # All-time MYR purchased & sold
    total_myr_purchased = db.query(func.coalesce(func.sum(Transaction.myr_quantity), Decimal("0"))).filter(
        Transaction.transaction_type == "PURCHASE", Transaction.status == "POSTED"
    ).scalar()

    total_myr_sold = db.query(func.coalesce(func.sum(Transaction.myr_quantity), Decimal("0"))).filter(
        Transaction.transaction_type == "SALE", Transaction.status == "POSTED"
    ).scalar()

    # 5. Cash position
    total_cash_bdt = db.query(func.coalesce(func.sum(CashAccount.current_balance), Decimal("0.00"))).scalar()

    # 6. Customer Receivables & Payables
    customer_receivables = db.query(func.coalesce(func.sum(Customer.total_receivable_bdt), Decimal("0.00"))).filter(
        Customer.is_archived == False
    ).scalar()

    customer_payables = db.query(func.coalesce(func.sum(Customer.total_payable_bdt), Decimal("0.00"))).filter(
        Customer.is_archived == False
    ).scalar()

    # 7. Recent Activities
    recent_purchases = (
        db.query(Transaction)
        .filter(Transaction.transaction_type == "PURCHASE")
        .order_by(desc(Transaction.transaction_date))
        .limit(5)
        .all()
    )

    recent_sales = (
        db.query(Transaction)
        .filter(Transaction.transaction_type == "SALE")
        .order_by(desc(Transaction.transaction_date))
        .limit(5)
        .all()
    )

    recent_payments = (
        db.query(Payment)
        .order_by(desc(Payment.payment_date))
        .limit(5)
        .all()
    )

    recent_expenses = (
        db.query(Expense)
        .order_by(desc(Expense.expense_date), desc(Expense.created_at))
        .limit(5)
        .all()
    )

    recent_customers = (
        db.query(Customer)
        .order_by(desc(Customer.created_at))
        .limit(5)
        .all()
    )

    # 8. Outstanding Payment Lists
    debtor_customers = (
        db.query(Customer)
        .filter(Customer.total_receivable_bdt > Decimal("0.00"))
        .order_by(desc(Customer.total_receivable_bdt))
        .limit(10)
        .all()
    )

    creditor_customers = (
        db.query(Customer)
        .filter(Customer.total_payable_bdt > Decimal("0.00"))
        .order_by(desc(Customer.total_payable_bdt))
        .limit(10)
        .all()
    )

    partially_paid_txs = (
        db.query(Transaction)
        .filter(Transaction.payment_status.in_(["PARTIALLY_PAID", "UNPAID"]), Transaction.status == "POSTED")
        .order_by(desc(Transaction.transaction_date))
        .limit(10)
        .all()
    )

    return {
        "cards": {
            "today_gross_profit": today_gross_profit,
            "today_net_profit": today_net_profit,
            "month_gross_profit": month_gross_profit,
            "month_net_profit": month_net_profit,
            "year_net_profit": year_net_profit,
            "total_myr_purchased": total_myr_purchased,
            "total_myr_sold": total_myr_sold,
            "current_myr_inventory": current_myr_qty,
            "current_myr_valuation": current_myr_val,
            "current_myr_wac": current_myr_wac,
            "total_bdt_cash": total_cash_bdt,
            "customer_receivables": customer_receivables,
            "company_payables": customer_payables,
            "year_operating_expenses": year_operating_expenses,
        },
        "recent_purchases": recent_purchases,
        "recent_sales": recent_sales,
        "recent_payments": recent_payments,
        "recent_expenses": recent_expenses,
        "recent_customers": recent_customers,
        "debtor_customers": debtor_customers,
        "creditor_customers": creditor_customers,
        "partially_paid_txs": partially_paid_txs,
    }


def get_dashboard_chart_data(db: Session, days: int = 14) -> dict:
    today = date.today()
    dates = [(today - timedelta(days=i)) for i in range(days - 1, -1, -1)]
    labels = [d.strftime("%d %b") for d in dates]

    daily_profit = []
    myr_purchases = []
    myr_sales = []

    for d in dates:
        pnl = get_profit_and_loss(db, from_date=d, to_date=d)
        daily_profit.append(float(pnl["net_profit"]))

        # MYR purchase volume
        p_qty = db.query(func.coalesce(func.sum(Transaction.myr_quantity), Decimal("0"))).filter(
            Transaction.transaction_type == "PURCHASE",
            Transaction.status == "POSTED",
            func.date(Transaction.transaction_date) == d,
        ).scalar()
        myr_purchases.append(float(p_qty))

        # MYR sales volume
        s_qty = db.query(func.coalesce(func.sum(Transaction.myr_quantity), Decimal("0"))).filter(
            Transaction.transaction_type == "SALE",
            Transaction.status == "POSTED",
            func.date(Transaction.transaction_date) == d,
        ).scalar()
        myr_sales.append(float(s_qty))

    # Expense breakdown by category
    categories = db.query(ExpenseCategory).all()
    expense_labels = []
    expense_data = []
    for cat in categories:
        exp_sum = db.query(func.coalesce(func.sum(Expense.amount_bdt), Decimal("0.00"))).filter(
            Expense.category_id == cat.id, Expense.status == "POSTED"
        ).scalar()
        if exp_sum > Decimal("0.00"):
            expense_labels.append(cat.name)
            expense_data.append(float(exp_sum))

    return {
        "labels": labels,
        "daily_profit": daily_profit,
        "myr_purchases": myr_purchases,
        "myr_sales": myr_sales,
        "expense_categories": {
            "labels": expense_labels,
            "data": expense_data,
        },
    }


def get_daily_financial_report(db: Session, target_date: date) -> dict:
    # Transactions for this date
    purchases = db.query(Transaction).filter(
        Transaction.transaction_type == "PURCHASE",
        Transaction.status == "POSTED",
        func.date(Transaction.transaction_date) == target_date,
    ).all()

    sales = db.query(Transaction).filter(
        Transaction.transaction_type == "SALE",
        Transaction.status == "POSTED",
        func.date(Transaction.transaction_date) == target_date,
    ).all()

    total_myr_purchased = sum((p.myr_quantity for p in purchases), Decimal("0"))
    total_purchase_val = sum((p.total_amount_bdt for p in purchases), Decimal("0"))

    total_myr_sold = sum((s.myr_quantity for s in sales), Decimal("0"))
    total_sales_val = sum((s.total_amount_bdt for s in sales), Decimal("0"))

    pnl = get_profit_and_loss(db, from_date=target_date, to_date=target_date)

    # Payments on this date
    incoming_payments = db.query(Payment).filter(
        Payment.payment_type == "INCOMING",
        func.date(Payment.payment_date) == target_date,
    ).all()
    total_incoming = sum((p.amount_bdt for p in incoming_payments), Decimal("0"))

    outgoing_payments = db.query(Payment).filter(
        Payment.payment_type == "OUTGOING",
        func.date(Payment.payment_date) == target_date,
    ).all()
    total_outgoing = sum((p.amount_bdt for p in outgoing_payments), Decimal("0"))

    # Outstanding balances as of target date
    cust_receivables = db.query(func.coalesce(func.sum(Customer.total_receivable_bdt), Decimal("0.00"))).scalar()
    cust_payables = db.query(func.coalesce(func.sum(Customer.total_payable_bdt), Decimal("0.00"))).scalar()

    # Cash balance
    cash_now = db.query(func.coalesce(func.sum(CashAccount.current_balance), Decimal("0.00"))).scalar()

    return {
        "date": target_date,
        "total_myr_purchased": total_myr_purchased,
        "total_purchase_val": total_purchase_val,
        "total_myr_sold": total_myr_sold,
        "total_sales_val": total_sales_val,
        "gross_profit": pnl["gross_profit"],
        "operating_expenses": pnl["total_operating_expenses"],
        "net_profit": pnl["net_profit"],
        "total_incoming_payments": total_incoming,
        "total_outgoing_payments": total_outgoing,
        "current_cash_balance": cash_now,
        "customer_receivables": cust_receivables,
        "company_payables": cust_payables,
        "purchases": purchases,
        "sales": sales,
    }


def get_monthly_financial_report(db: Session, year: int, month: int) -> dict:
    from_date = date(year, month, 1)
    if month == 12:
        to_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        to_date = date(year, month + 1, 1) - timedelta(days=1)

    pnl = get_profit_and_loss(db, from_date=from_date, to_date=to_date)
    cash_flow = get_cash_flow_statement(db, from_date=from_date, to_date=to_date)

    # MYR purchased & sold during month
    myr_purchased = db.query(func.coalesce(func.sum(Transaction.myr_quantity), Decimal("0"))).filter(
        Transaction.transaction_type == "PURCHASE",
        Transaction.status == "POSTED",
        func.date(Transaction.transaction_date) >= from_date,
        func.date(Transaction.transaction_date) <= to_date,
    ).scalar()

    purchase_val = db.query(func.coalesce(func.sum(Transaction.total_amount_bdt), Decimal("0.00"))).filter(
        Transaction.transaction_type == "PURCHASE",
        Transaction.status == "POSTED",
        func.date(Transaction.transaction_date) >= from_date,
        func.date(Transaction.transaction_date) <= to_date,
    ).scalar()

    myr_sold = db.query(func.coalesce(func.sum(Transaction.myr_quantity), Decimal("0"))).filter(
        Transaction.transaction_type == "SALE",
        Transaction.status == "POSTED",
        func.date(Transaction.transaction_date) >= from_date,
        func.date(Transaction.transaction_date) <= to_date,
    ).scalar()

    # Receivables & Payables
    cust_receivables = db.query(func.coalesce(func.sum(Customer.total_receivable_bdt), Decimal("0.00"))).scalar()
    cust_payables = db.query(func.coalesce(func.sum(Customer.total_payable_bdt), Decimal("0.00"))).scalar()

    # Inventory Valuation
    myr_inv = db.query(CurrencyInventory).filter_by(currency_code="MYR").first()

    return {
        "year": year,
        "month": month,
        "from_date": from_date,
        "to_date": to_date,
        "sales_revenue": pnl["total_revenue"],
        "cogs": pnl["total_cogs"],
        "gross_profit": pnl["gross_profit"],
        "operating_expenses": pnl["total_operating_expenses"],
        "net_profit": pnl["net_profit"],
        "myr_purchased": myr_purchased,
        "purchase_value": purchase_val,
        "myr_sold": myr_sold,
        "cash_flow": cash_flow,
        "customer_receivables": cust_receivables,
        "company_payables": cust_payables,
        "inventory_qty": myr_inv.total_quantity if myr_inv else Decimal("0"),
        "inventory_valuation": myr_inv.total_valuation_bdt if myr_inv else Decimal("0"),
        "pnl_details": pnl,
    }


def get_yearly_financial_report(db: Session, year: int) -> dict:
    from_date = date(year, 1, 1)
    to_date = date(year, 12, 31)

    pnl = get_profit_and_loss(db, from_date=from_date, to_date=to_date)
    cash_flow = get_cash_flow_statement(db, from_date=from_date, to_date=to_date)

    myr_purchased = db.query(func.coalesce(func.sum(Transaction.myr_quantity), Decimal("0"))).filter(
        Transaction.transaction_type == "PURCHASE",
        Transaction.status == "POSTED",
        func.date(Transaction.transaction_date) >= from_date,
        func.date(Transaction.transaction_date) <= to_date,
    ).scalar()

    purchase_val = db.query(func.coalesce(func.sum(Transaction.total_amount_bdt), Decimal("0.00"))).filter(
        Transaction.transaction_type == "PURCHASE",
        Transaction.status == "POSTED",
        func.date(Transaction.transaction_date) >= from_date,
        func.date(Transaction.transaction_date) <= to_date,
    ).scalar()

    myr_sold = db.query(func.coalesce(func.sum(Transaction.myr_quantity), Decimal("0"))).filter(
        Transaction.transaction_type == "SALE",
        Transaction.status == "POSTED",
        func.date(Transaction.transaction_date) >= from_date,
        func.date(Transaction.transaction_date) <= to_date,
    ).scalar()

    cust_receivables = db.query(func.coalesce(func.sum(Customer.total_receivable_bdt), Decimal("0.00"))).scalar()
    cust_payables = db.query(func.coalesce(func.sum(Customer.total_payable_bdt), Decimal("0.00"))).scalar()
    myr_inv = db.query(CurrencyInventory).filter_by(currency_code="MYR").first()

    return {
        "year": year,
        "from_date": from_date,
        "to_date": to_date,
        "sales_revenue": pnl["total_revenue"],
        "cogs": pnl["total_cogs"],
        "gross_profit": pnl["gross_profit"],
        "operating_expenses": pnl["total_operating_expenses"],
        "net_profit": pnl["net_profit"],
        "myr_purchased": myr_purchased,
        "purchase_value": purchase_val,
        "myr_sold": myr_sold,
        "cash_flow": cash_flow,
        "customer_receivables": cust_receivables,
        "company_payables": cust_payables,
        "inventory_qty": myr_inv.total_quantity if myr_inv else Decimal("0"),
        "inventory_valuation": myr_inv.total_valuation_bdt if myr_inv else Decimal("0"),
        "pnl_details": pnl,
    }
