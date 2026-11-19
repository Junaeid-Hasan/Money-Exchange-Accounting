from decimal import Decimal
from app.models import User, CashAccount
from app.services.customer_service import create_customer
from app.services.transaction_service import create_purchase_transaction
from app.services.payment_service import record_outgoing_payment


def test_purchase_and_installment_lifecycle(db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()

    # 1. Register customer Rahim Ahmed
    customer = create_customer(
        db=db_session,
        full_name="Rahim Ahmed",
        phone_number="+880 1711-111111",
        user_id=admin.id,
    )

    # 2. Purchase 100 MYR at ৳300. Total = ৳30,000. Pay ৳20,000.
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

    # Expected: Total = ৳30,000, Paid = ৳20,000, Outstanding Payable = ৳10,000
    assert tx.total_amount_bdt == Decimal("30000.00")
    assert tx.paid_amount_bdt == Decimal("20000.00")
    assert tx.outstanding_amount_bdt == Decimal("10000.00")
    assert tx.payment_status == "PARTIALLY_PAID"

    db_session.refresh(customer)
    assert customer.total_payable_bdt == Decimal("10000.00")
    assert customer.total_receivable_bdt == Decimal("0.00")

    # 3. Make installment payment of ৳5,000. Expected payable = ৳5,000.
    pay1 = record_outgoing_payment(
        db=db_session,
        transaction_id=tx.id,
        amount=Decimal("5000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
        notes="First installment",
    )

    db_session.refresh(tx)
    db_session.refresh(customer)
    assert tx.paid_amount_bdt == Decimal("25000.00")
    assert tx.outstanding_amount_bdt == Decimal("5000.00")
    assert tx.payment_status == "PARTIALLY_PAID"
    assert customer.total_payable_bdt == Decimal("5000.00")

    # 4. Make final payment of ৳5,000. Expected payable = ৳0.
    pay2 = record_outgoing_payment(
        db=db_session,
        transaction_id=tx.id,
        amount=Decimal("5000.00"),
        cash_account_id=cash_acc.id,
        payment_method="CASH",
        created_by_id=admin.id,
        notes="Final installment settlement",
    )

    db_session.refresh(tx)
    db_session.refresh(customer)
    assert tx.paid_amount_bdt == Decimal("30000.00")
    assert tx.outstanding_amount_bdt == Decimal("0.00")
    assert tx.payment_status == "FULLY_PAID"
    assert customer.total_payable_bdt == Decimal("0.00")
