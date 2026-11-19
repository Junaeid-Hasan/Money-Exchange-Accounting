import pytest
from decimal import Decimal
from app.models import User, CashAccount, CurrencyInventory
from app.services.customer_service import create_customer
from app.services.transaction_service import create_purchase_transaction, create_sales_transaction
from app.services.accounting_service import get_profit_and_loss


def test_inventory_moving_wac_and_valuation(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()
    customer = create_customer(db_session, "Inventory Trader", "+880 1733-333333", user_id=admin.id)

    # Step 1: Purchase 100 MYR at ৳300 = ৳30,000
    create_purchase_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("100.00"),
        purchase_rate=Decimal("300.0000"),
        initial_payment=Decimal("30000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    inv = db_session.query(CurrencyInventory).filter_by(currency_code="MYR").first()
    assert inv.total_quantity == Decimal("100.0000")
    assert inv.weighted_average_cost == Decimal("300.0000")
    assert inv.total_valuation_bdt == Decimal("30000.00")

    # Step 2: Purchase another 100 MYR at ৳320 = ৳32,000
    create_purchase_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("100.00"),
        purchase_rate=Decimal("320.0000"),
        initial_payment=Decimal("32000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    db_session.refresh(inv)
    # Expected inventory = 200 MYR
    assert inv.total_quantity == Decimal("200.0000")
    # Expected weighted average cost = (30,000 + 32,000) / 200 = ৳310.00
    assert inv.weighted_average_cost == Decimal("310.0000")
    assert inv.total_valuation_bdt == Decimal("62000.00")

    # Step 3: Sell 50 MYR (e.g. at ৳330)
    tx_sale = create_sales_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("50.00"),
        selling_rate=Decimal("330.0000"),
        initial_payment=Decimal("16500.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # COGS = 50 * 310 = ৳15,500
    assert tx_sale.cogs_bdt == Decimal("15500.00")

    db_session.refresh(inv)
    # Expected remaining inventory = 150 MYR
    assert inv.total_quantity == Decimal("150.0000")
    # Expected remaining inventory valuation = 62,000 - 15,500 = ৳46,500
    assert inv.total_valuation_bdt == Decimal("46500.00")
    # WAC remains unchanged after a sale
    assert inv.weighted_average_cost == Decimal("310.0000")


def test_gross_profit_calculation(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()
    customer = create_customer(db_session, "Profit Partner", "+880 1744-444444", user_id=admin.id)

    # Purchase 100 MYR at ৳300 = ৳30,000
    create_purchase_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("100.00"),
        purchase_rate=Decimal("300.0000"),
        initial_payment=Decimal("30000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # Sell 100 MYR at ৳310 = ৳31,000
    create_sales_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("100.00"),
        selling_rate=Decimal("310.0000"),
        initial_payment=Decimal("31000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # Check P&L
    pnl = get_profit_and_loss(db_session)
    assert pnl["total_revenue"] == Decimal("31000.00")
    assert pnl["total_cogs"] == Decimal("30000.00")
    # Expected gross profit = ৳1,000
    assert pnl["gross_profit"] == Decimal("1000.00")
