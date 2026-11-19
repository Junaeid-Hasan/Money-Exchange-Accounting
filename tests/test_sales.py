from decimal import Decimal
from app.models import User, CashAccount
from app.services.customer_service import create_customer
from app.services.transaction_service import create_purchase_transaction, create_sales_transaction
from app.services.payment_service import record_incoming_payment


def test_sales_and_collection_lifecycle(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()

    supplier = create_customer(db_session, "Supplier Client", "+880 1700-000001", user_id=admin.id)
    buyer = create_customer(db_session, "Karim Ahmed", "+880 1722-222222", user_id=admin.id)

    # Initial inventory: Purchase 100 MYR @ ৳300
    create_purchase_transaction(
        db=db_session,
        customer_id=supplier.id,
        myr_quantity=Decimal("100.00"),
        purchase_rate=Decimal("300.0000"),
        initial_payment=Decimal("30000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # 1. Sell 100 MYR at ৳310. Total = ৳31,000. Receive ৳21,000.
    tx = create_sales_transaction(
        db=db_session,
        customer_id=buyer.id,
        myr_quantity=Decimal("100.00"),
        selling_rate=Decimal("310.0000"),
        initial_payment=Decimal("21000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
    )

    # Expected: Total = ৳31,000, Paid = ৳21,000, Outstanding Receivable = ৳10,000
    assert tx.total_amount_bdt == Decimal("31000.00")
    assert tx.paid_amount_bdt == Decimal("21000.00")
    assert tx.outstanding_amount_bdt == Decimal("10000.00")
    assert tx.payment_status == "PARTIALLY_PAID"

    db_session.refresh(buyer)
    assert buyer.total_receivable_bdt == Decimal("10000.00")
    assert buyer.total_payable_bdt == Decimal("0.00")

    # 2. Receive remaining ৳10,000. Expected receivable = ৳0.
    pay = record_incoming_payment(
        db=db_session,
        transaction_id=tx.id,
        amount=Decimal("10000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
        notes="Final balance collection",
    )

    db_session.refresh(tx)
    db_session.refresh(buyer)
    assert tx.paid_amount_bdt == Decimal("31000.00")
    assert tx.outstanding_amount_bdt == Decimal("0.00")
    assert tx.payment_status == "FULLY_PAID"
    assert buyer.total_receivable_bdt == Decimal("0.00")
