import pytest
from decimal import Decimal
from app.models import User, CashAccount, CurrencyInventory, Transaction
from app.services.customer_service import create_customer
from app.services.rate_service import update_exchange_rates
from app.services.transaction_service import (
    create_purchase_transaction,
    create_sales_transaction,
    void_cancel_transaction,
)
from app.services.payment_service import record_incoming_payment
from app.services.accounting_service import (
    get_trial_balance,
    get_balance_sheet,
    get_profit_and_loss,
)


def test_double_entry_balance_sheet_and_trial_balance(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()
    customer = create_customer(db_session, "Integrity Client", "+880 1755-555555", user_id=admin.id)

    # 1. Buy 100 MYR @ ৳300 = ৳30,000 (Paid ৳20,000, ৳10,000 AP)
    tx_pur = create_purchase_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("100.00"),
        purchase_rate=Decimal("300.0000"),
        initial_payment=Decimal("20000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # 2. Sell 50 MYR @ ৳320 = ৳16,000 (Received ৳10,000, ৳6,000 AR)
    tx_sal = create_sales_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("50.00"),
        selling_rate=Decimal("320.0000"),
        initial_payment=Decimal("10000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # 3. Check Trial Balance
    tb = get_trial_balance(db_session)
    assert tb["is_balanced"] is True
    assert tb["total_debits"] == tb["total_credits"]

    # 4. Check Balance Sheet (Assets == Liabilities + Equity)
    bs = get_balance_sheet(db_session)
    assert bs["is_balanced"] is True
    assert bs["total_assets"] == bs["total_liabilities_and_equity"]


def test_payment_does_not_create_duplicate_revenue(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()
    customer = create_customer(db_session, "Revenue Verification", "+880 1766-666666", user_id=admin.id)

    # Buy 100 MYR @ ৳300
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

    # Sell 100 MYR @ ৳310 = ৳31,000 (Receive ৳20,000, Due ৳11,000)
    tx_sal = create_sales_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("100.00"),
        selling_rate=Decimal("310.0000"),
        initial_payment=Decimal("20000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    pnl_before = get_profit_and_loss(db_session)
    assert pnl_before["total_revenue"] == Decimal("31000.00")

    # Customer pays remaining ৳11,000 installment
    record_incoming_payment(
        db=db_session,
        transaction_id=tx_sal.id,
        amount=Decimal("11000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # Verify revenue did NOT increase from the installment collection
    pnl_after = get_profit_and_loss(db_session)
    assert pnl_after["total_revenue"] == Decimal("31000.00")
    assert pnl_after["gross_profit"] == Decimal("1000.00")


def test_negative_inventory_prevention(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()
    customer = create_customer(db_session, "Negative Stock Tester", "+880 1777-777777", user_id=admin.id)

    # Inventory is currently 0 MYR. Attempt to sell 50 MYR.
    with pytest.raises(ValueError) as excinfo:
        create_sales_transaction(
            db=db_session,
            customer_id=customer.id,
            myr_quantity=Decimal("50.00"),
            selling_rate=Decimal("310.0000"),
            initial_payment=Decimal("15500.00"),
            cash_account_id=cash_acc.id,
            payment_method="CASH",
            created_by_id=admin.id,
        )
    assert "Insufficient MYR inventory" in str(excinfo.value)


def test_rate_modification_does_not_alter_past_transactions(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()
    customer = create_customer(db_session, "Rate Client", "+880 1788-888888", user_id=admin.id)

    # Buy at current rate ৳300
    tx = create_purchase_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("100.00"),
        purchase_rate=Decimal("300.0000"),
        initial_payment=Decimal("30000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # Admin updates default rates to ৳340 / ৳350
    update_exchange_rates(
        db=db_session,
        purchase_rate=Decimal("340.0000"),
        selling_rate=Decimal("350.0000"),
        user_id=admin.id,
    )

    # Check that previous transaction permanently retains ৳300
    db_session.refresh(tx)
    assert tx.exchange_rate == Decimal("300.0000")
    assert tx.total_amount_bdt == Decimal("30000.00")


def test_transaction_reversal_integrity(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()
    customer = create_customer(db_session, "Reversal Client", "+880 1799-999999", user_id=admin.id)

    # Purchase 100 MYR @ ৳300 (Pay ৳20,000, ৳10,000 AP)
    tx = create_purchase_transaction(
        db=db_session,
        customer_id=customer.id,
        myr_quantity=Decimal("100.00"),
        purchase_rate=Decimal("300.0000"),
        initial_payment=Decimal("20000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    inv = db_session.query(CurrencyInventory).filter_by(currency_code="MYR").first()
    assert inv.total_quantity == Decimal("100.0000")
    assert customer.total_payable_bdt == Decimal("10000.00")

    # Cancel transaction
    void_cancel_transaction(
        db=db_session,
        transaction_id=tx.id,
        reason="Entry mistake",
        user_id=admin.id,
    )

    db_session.refresh(tx)
    db_session.refresh(inv)
    db_session.refresh(customer)

    assert tx.status == "CANCELLED"
    assert inv.total_quantity == Decimal("0.0000")
    assert customer.total_payable_bdt == Decimal("0.00")

    # Trial Balance must remain balanced
    tb = get_trial_balance(db_session)
    assert tb["is_balanced"] is True
    assert tb["total_debits"] == tb["total_credits"]
