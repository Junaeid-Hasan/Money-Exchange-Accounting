import pytest
from decimal import Decimal
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app as fastapi_app

# In-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    from app.models import Role, User, ChartOfAccount, CashAccount, CurrencyInventory, ExchangeRate, CompanySettings
    from app.services.auth_service import hash_password
    from datetime import datetime, timezone

    # 1. Seed Roles
    admin_role = Role(code="ADMIN", name="Administrator", permissions={"can_all": True})
    staff_role = Role(code="STAFF", name="Staff", permissions={"can_tx": True})
    db.add_all([admin_role, staff_role])
    db.flush()

    # 2. Seed Admin User
    admin = User(
        username="admin",
        email="admin@test.com",
        password_hash=hash_password("admin123"),
        full_name="Admin User",
        role_code="ADMIN",
        is_active=True,
    )
    db.add(admin)
    db.flush()

    # 3. Seed COA
    coa_list = [
        ChartOfAccount(account_code="1010", account_name="Cash in Hand (BDT)", account_type="ASSET", normal_balance="DEBIT"),
        ChartOfAccount(account_code="1020", account_name="Bank Account (BDT)", account_type="ASSET", normal_balance="DEBIT"),
        ChartOfAccount(account_code="1030", account_name="Accounts Receivable", account_type="ASSET", normal_balance="DEBIT"),
        ChartOfAccount(account_code="1040", account_name="MYR Currency Inventory", account_type="ASSET", normal_balance="DEBIT"),
        ChartOfAccount(account_code="2010", account_name="Accounts Payable", account_type="LIABILITY", normal_balance="CREDIT"),
        ChartOfAccount(account_code="3010", account_name="Owner's Capital", account_type="EQUITY", normal_balance="CREDIT"),
        ChartOfAccount(account_code="3020", account_name="Retained Earnings", account_type="EQUITY", normal_balance="CREDIT"),
        ChartOfAccount(account_code="3030", account_name="Current Period Earnings", account_type="EQUITY", normal_balance="CREDIT"),
        ChartOfAccount(account_code="4010", account_name="MYR Sales Revenue", account_type="INCOME", normal_balance="CREDIT"),
        ChartOfAccount(account_code="4030", account_name="Miscellaneous Other Income", account_type="INCOME", normal_balance="CREDIT"),
        ChartOfAccount(account_code="5010", account_name="Cost of Goods Sold - MYR", account_type="EXPENSE", normal_balance="DEBIT"),
        ChartOfAccount(account_code="6010", account_name="Office Rent Expense", account_type="EXPENSE", normal_balance="DEBIT"),
        ChartOfAccount(account_code="6080", account_name="Cash Shortage Loss", account_type="EXPENSE", normal_balance="DEBIT"),
    ]
    db.add_all(coa_list)
    db.flush()

    # 4. Cash Account
    cash_gl = db.query(ChartOfAccount).filter_by(account_code="1010").first()
    cash_acc = CashAccount(
        account_code="CASH_MAIN",
        account_name="Cash Counter 1",
        account_type="CASH",
        gl_account_id=cash_gl.id,
        current_balance=Decimal("100000.00"),  # Initial cash float for payouts
    )
    db.add(cash_acc)

    # 5. Inventory
    inv = CurrencyInventory(
        currency_code="MYR",
        total_quantity=Decimal("0.0000"),
        weighted_average_cost=Decimal("0.0000"),
        total_valuation_bdt=Decimal("0.00"),
    )
    db.add(inv)

    # 6. Default rate
    rate = ExchangeRate(
        currency_code="MYR",
        default_purchase_rate=Decimal("300.0000"),
        default_selling_rate=Decimal("310.0000"),
        effective_from=datetime.now(timezone.utc),
        is_active=True,
        created_by_id=admin.id,
    )
    db.add(rate)

    # 7. Settings
    settings = CompanySettings(company_name="Test Forex Ltd.")
    db.add(settings)

    db.commit()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
