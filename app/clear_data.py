from decimal import Decimal
from app.database import SessionLocal
from app.models import (
    Customer,
    Transaction,
    Payment,
    JournalEntry,
    JournalEntryLine,
    InventoryMovement,
    CashMovement,
    Expense,
    DailyCashReconciliation,
    AuditLog,
    CashAccount,
    CurrencyInventory,
)


def purge_all_dummy_data():
    """
    Purges all transactional records, customer records, payments, expenses, 
    journal entries, inventory movements, cash movements, and audit logs.
    Resets cash account balances to ৳0.00 and currency inventory to 0.0000 MYR.
    Preserves Chart of Accounts, Roles, Users, Company Settings, and Exchange Rates.
    """
    db = SessionLocal()
    try:
        print("Starting dummy data purge...")

        # 1. Delete dependent accounting and movement lines
        deleted_lines = db.query(JournalEntryLine).delete(synchronize_session=False)
        deleted_journals = db.query(JournalEntry).delete(synchronize_session=False)
        deleted_inv_movs = db.query(InventoryMovement).delete(synchronize_session=False)
        deleted_cash_movs = db.query(CashMovement).delete(synchronize_session=False)

        # 2. Delete payments and transactions
        deleted_payments = db.query(Payment).delete(synchronize_session=False)
        deleted_transactions = db.query(Transaction).delete(synchronize_session=False)

        # 3. Delete expenses, reconciliations, customers, and audit logs
        deleted_expenses = db.query(Expense).delete(synchronize_session=False)
        deleted_recons = db.query(DailyCashReconciliation).delete(synchronize_session=False)
        deleted_customers = db.query(Customer).delete(synchronize_session=False)
        deleted_audits = db.query(AuditLog).delete(synchronize_session=False)

        # 4. Reset Cash Accounts balance to 0.00
        cash_accounts = db.query(CashAccount).all()
        for ca in cash_accounts:
            ca.current_balance = Decimal("0.00")

        # 5. Reset Currency Inventory (MYR) to 0.0000
        inventories = db.query(CurrencyInventory).all()
        for inv in inventories:
            inv.total_quantity = Decimal("0.0000")
            inv.weighted_average_cost = Decimal("0.0000")
            inv.total_valuation_bdt = Decimal("0.00")

        db.commit()

        print("=== Purge Summary ===")
        print(f"Journal Lines deleted: {deleted_lines}")
        print(f"Journal Entries deleted: {deleted_journals}")
        print(f"Inventory Movements deleted: {deleted_inv_movs}")
        print(f"Cash Movements deleted: {deleted_cash_movs}")
        print(f"Payments deleted: {deleted_payments}")
        print(f"Transactions deleted: {deleted_transactions}")
        print(f"Expenses deleted: {deleted_expenses}")
        print(f"Reconciliations deleted: {deleted_recons}")
        print(f"Customers deleted: {deleted_customers}")
        print(f"Audit Logs deleted: {deleted_audits}")
        print("Cash accounts reset to: ৳0.00")
        print("Currency inventory reset to: 0.0000 MYR")
        print("Dummy data purge completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error purging data: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    purge_all_dummy_data()
