from decimal import Decimal
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models import User, CashAccount
from app.services.customer_service import create_customer
from app.services.transaction_service import create_purchase_transaction, create_sales_transaction
from app.services.payment_service import record_incoming_payment, record_outgoing_payment
from app.services.expense_service import create_expense
from app.models import ExpenseCategory
from datetime import date


def populate_demo_data():
    db = SessionLocal()
    try:
        admin = db.query(User).filter_by(username="admin").first()
        cash_acc = db.query(CashAccount).filter_by(account_code="CASH_MAIN").first()

        # Check if demo customer already exists
        cust1 = create_customer(
            db=db,
            full_name="Rahim Ahmed",
            phone_number="+880 1711-223344",
            address="Gulshan-2, Dhaka",
            national_id="NID-198826912345",
            notes="Regular Ringgit supplier from expatriate remittances",
            user_id=admin.id,
        )

        cust2 = create_customer(
            db=db,
            full_name="Karim Ullah",
            phone_number="+880 1819-556677",
            address="Agrabad Commercial Area, Chittagong",
            national_id="NID-199215098765",
            notes="Business travel client",
            user_id=admin.id,
        )

        # 1. Purchase: Rahim sells 500 MYR @ ৳300 = ৳150,000 (Paid ৳100,000, ৳50,000 due)
        tx_pur = create_purchase_transaction(
            db=db,
            customer_id=cust1.id,
            myr_quantity=Decimal("500.00"),
            purchase_rate=Decimal("300.0000"),
            initial_payment=Decimal("100000.00"),
            cash_account_id=cash_acc.id,
            payment_method="CASH",
            created_by_id=admin.id,
            notes="Remittance exchange",
        )

        # 2. Purchase: Buy another 500 MYR @ ৳320 = ৳160,000 (Paid fully)
        tx_pur2 = create_purchase_transaction(
            db=db,
            customer_id=cust1.id,
            myr_quantity=Decimal("500.00"),
            purchase_rate=Decimal("320.0000"),
            initial_payment=Decimal("160000.00"),
            cash_account_id=cash_acc.id,
            payment_method="CASH",
            created_by_id=admin.id,
            notes="Expatriate batch purchase",
        )

        # 3. Sale: Karim buys 300 MYR @ ৳330 = ৳99,000 (Paid ৳69,000, ৳30,000 due)
        tx_sal = create_sales_transaction(
            db=db,
            customer_id=cust2.id,
            myr_quantity=Decimal("300.00"),
            selling_rate=Decimal("330.0000"),
            initial_payment=Decimal("69000.00"),
            cash_account_id=cash_acc.id,
            payment_method="CASH",
            created_by_id=admin.id,
            notes="Travel allowance",
        )

        # 4. Partial settlement: Karim pays ৳15,000 towards due
        record_incoming_payment(
            db=db,
            transaction_id=tx_sal.id,
            amount=Decimal("15000.00"),
            cash_account_id=cash_acc.id,
            payment_method="CASH",
            created_by_id=admin.id,
            notes="Installment 1",
        )

        # 5. Operating expenses: Office rent & Internet
        rent_cat = db.query(ExpenseCategory).filter_by(name="Office Rent").first()
        if rent_cat:
            create_expense(
                db=db,
                category_id=rent_cat.id,
                amount_bdt=Decimal("20000.00"),
                cash_account_id=cash_acc.id,
                expense_date=date.today(),
                description="Monthly branch rent",
                created_by_id=admin.id,
            )

        print("Demo financial transactions and customer accounts populated successfully!")
    except Exception as e:
        print(f"Demo population note: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    populate_demo_data()
