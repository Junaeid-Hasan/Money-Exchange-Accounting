from decimal import Decimal
from app.models import User, CashAccount
from app.services.customer_service import create_customer
from app.services.transaction_service import create_purchase_transaction, create_sales_transaction
from app.services.auth_service import create_access_token


def test_api_chart_data_and_web_routes(client, db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    token = create_access_token(data={"sub": admin.username, "role": admin.role_code})
    client.cookies.set("access_token", f"Bearer {token}")

    # 1. Test Dashboard Route
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Financial Operations Dashboard" in resp.text

    # 2. Test Chart Data API
    chart_resp = client.get("/api/v1/reports/chart-data")
    assert chart_resp.status_code == 200
    data = chart_resp.json()
    assert "labels" in data
    assert "daily_profit" in data
    assert "myr_purchases" in data
    assert "myr_sales" in data

    # 3. Test Customers List
    resp = client.get("/customers")
    assert resp.status_code == 200
    assert "Customer Management" in resp.text

    # 4. Test Rates View
    resp = client.get("/rates")
    assert resp.status_code == 200
    assert "Company Exchange Rate Management" in resp.text

    # 5. Test Transactions List
    resp = client.get("/transactions")
    assert resp.status_code == 200
    assert "Transaction Management" in resp.text

    # 6. Test Inventory View
    resp = client.get("/inventory")
    assert resp.status_code == 200
    assert "Malaysian Ringgit (MYR) Inventory" in resp.text

    # 7. Test Cash & Bank View
    resp = client.get("/cash-bank")
    assert resp.status_code == 200
    assert "Cash & Bank Treasury Management" in resp.text

    # 8. Test Expenses View
    resp = client.get("/expenses")
    assert resp.status_code == 200
    assert "Operating Expense Management" in resp.text

    # 9. Test Chart of Accounts View
    resp = client.get("/accounting/chart-of-accounts")
    assert resp.status_code == 200
    assert "Chart of Accounts" in resp.text

    # 10. Test Journal Entries View
    resp = client.get("/accounting/journal-entries")
    assert resp.status_code == 200
    assert "Double-Entry Journal Entries" in resp.text

    # 11. Test Trial Balance View
    resp = client.get("/accounting/trial-balance")
    assert resp.status_code == 200
    assert "General Ledger Trial Balance" in resp.text

    # 12. Test Reports View
    resp = client.get("/reports")
    assert resp.status_code == 200
    assert "Financial Statements & Reporting Center" in resp.text

    # 13. Test Balance Sheet View
    resp = client.get("/reports/balance-sheet")
    assert resp.status_code == 200
    assert "Balance Sheet" in resp.text

    # 14. Test Profit and Loss View
    resp = client.get("/reports/profit-loss")
    assert resp.status_code == 200
    assert "Profit & Loss Statement" in resp.text

    # 15. Test Daily Report View
    resp = client.get("/reports/daily")
    assert resp.status_code == 200
    assert "Daily Operational Financial Report" in resp.text


def test_pdf_and_excel_exports(client, db_session):
    admin = db_session.query(User).filter_by(username="admin").first()
    cash_acc = db_session.query(CashAccount).filter_by(account_code="CASH_MAIN").first()
    token = create_access_token(data={"sub": admin.username, "role": admin.role_code})
    client.cookies.set("access_token", f"Bearer {token}")

    customer = create_customer(db_session, "PDF Export Client", "+880 1788-123456", user_id=admin.id)
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

    # 1. Transaction Receipt PDF
    resp = client.get(f"/transactions/{tx.id}/receipt/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 500

    # 2. Customer Statement PDF
    resp = client.get(f"/customers/{customer.id}/statement/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 500

    # 3. Balance Sheet PDF
    resp = client.get("/reports/balance-sheet/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 500

    # 4. Transactions Excel Export
    resp = client.get("/transactions/export/excel")
    assert resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in resp.headers["content-type"]
    assert len(resp.content) > 500
