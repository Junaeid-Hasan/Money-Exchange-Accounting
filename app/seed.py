import bcrypt
from datetime import datetime, timezone
from decimal import Decimal
from app.database import SessionLocal
from app.models import (
    Role,
    User,
    ChartOfAccount,
    CashAccount,
    CurrencyInventory,
    ExchangeRate,
    CompanySettings,
    ExpenseCategory,
)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def seed_database():
    db = SessionLocal()
    try:
        # 1. Seed Roles
        roles_data = [
            {
                "code": "ADMIN",
                "name": "Administrator",
                "permissions": {
                    "can_manage_users": True,
                    "can_manage_rates": True,
                    "can_view_all_reports": True,
                    "can_manage_settings": True,
                    "can_manage_accounting": True,
                    "can_void_transactions": True,
                    "can_manage_customers": True,
                    "can_create_transactions": True,
                    "can_manage_expenses": True,
                    "can_reconcile_cash": True,
                },
            },
            {
                "code": "ACCOUNTANT",
                "name": "Accountant",
                "permissions": {
                    "can_manage_users": False,
                    "can_manage_rates": False,
                    "can_view_all_reports": True,
                    "can_manage_settings": False,
                    "can_manage_accounting": True,
                    "can_void_transactions": False,
                    "can_manage_customers": True,
                    "can_create_transactions": True,
                    "can_manage_expenses": True,
                    "can_reconcile_cash": True,
                },
            },
            {
                "code": "STAFF",
                "name": "Staff / Cashier",
                "permissions": {
                    "can_manage_users": False,
                    "can_manage_rates": False,
                    "can_view_all_reports": False,
                    "can_manage_settings": False,
                    "can_manage_accounting": False,
                    "can_void_transactions": False,
                    "can_manage_customers": True,
                    "can_create_transactions": True,
                    "can_manage_expenses": False,
                    "can_reconcile_cash": False,
                },
            },
        ]

        for r in roles_data:
            existing_role = db.query(Role).filter_by(code=r["code"]).first()
            if not existing_role:
                db.add(Role(**r))
        db.commit()

        # 2. Seed Users
        admin_user = db.query(User).filter_by(username="admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@forex-exchange.com.bd",
                password_hash=hash_password("admin123"),
                full_name="Chief Executive Administrator",
                role_code="ADMIN",
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        staff_user = db.query(User).filter_by(username="staff").first()
        if not staff_user:
            staff_user = User(
                username="staff",
                email="cashier1@forex-exchange.com.bd",
                password_hash=hash_password("staff123"),
                full_name="Exchange Counter Cashier",
                role_code="STAFF",
                is_active=True,
            )
            db.add(staff_user)
            db.commit()

        # 3. Seed Chart of Accounts
        coa_data = [
            # ASSETS (1000)
            {"account_code": "1010", "account_name": "Cash in Hand (BDT)", "account_type": "ASSET", "normal_balance": "DEBIT"},
            {"account_code": "1020", "account_name": "Bank Account (BDT)", "account_type": "ASSET", "normal_balance": "DEBIT"},
            {"account_code": "1025", "account_name": "Mobile Financial Services (bKash/Nagad)", "account_type": "ASSET", "normal_balance": "DEBIT"},
            {"account_code": "1030", "account_name": "Accounts Receivable (Customer Debits)", "account_type": "ASSET", "normal_balance": "DEBIT"},
            {"account_code": "1040", "account_name": "MYR Currency Inventory", "account_type": "ASSET", "normal_balance": "DEBIT"},
            {"account_code": "1050", "account_name": "Advance & Security Deposits", "account_type": "ASSET", "normal_balance": "DEBIT"},
            # LIABILITIES (2000)
            {"account_code": "2010", "account_name": "Accounts Payable (Customer Credits)", "account_type": "LIABILITY", "normal_balance": "CREDIT"},
            {"account_code": "2020", "account_name": "Accrued Expenses Payable", "account_type": "LIABILITY", "normal_balance": "CREDIT"},
            # EQUITY (3000)
            {"account_code": "3010", "account_name": "Owner's Capital", "account_type": "EQUITY", "normal_balance": "CREDIT"},
            {"account_code": "3020", "account_name": "Retained Earnings", "account_type": "EQUITY", "normal_balance": "CREDIT"},
            {"account_code": "3030", "account_name": "Current Period Earnings Summary", "account_type": "EQUITY", "normal_balance": "CREDIT"},
            # INCOME (4000)
            {"account_code": "4010", "account_name": "MYR Sales Revenue", "account_type": "INCOME", "normal_balance": "CREDIT"},
            {"account_code": "4020", "account_name": "Realized Foreign Exchange Gain", "account_type": "INCOME", "normal_balance": "CREDIT"},
            {"account_code": "4030", "account_name": "Miscellaneous Other Income", "account_type": "INCOME", "normal_balance": "CREDIT"},
            # COST OF GOODS SOLD (5000)
            {"account_code": "5010", "account_name": "Cost of Goods Sold - MYR", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            # OPERATING EXPENSES (6000)
            {"account_code": "6010", "account_name": "Office Rent Expense", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            {"account_code": "6020", "account_name": "Employee Salaries & Allowances", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            {"account_code": "6030", "account_name": "Electricity & Utilities", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            {"account_code": "6040", "account_name": "Internet & Communication", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            {"account_code": "6050", "account_name": "Conveyance & Local Travel", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            {"account_code": "6060", "account_name": "Bank Charges & Processing Fees", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            {"account_code": "6070", "account_name": "Office Maintenance & Printing", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            {"account_code": "6080", "account_name": "Cash Shortage / Overplus Loss", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
            {"account_code": "6090", "account_name": "Miscellaneous General Expenses", "account_type": "EXPENSE", "normal_balance": "DEBIT"},
        ]

        coa_map = {}
        for c in coa_data:
            existing_account = db.query(ChartOfAccount).filter_by(account_code=c["account_code"]).first()
            if not existing_account:
                account = ChartOfAccount(**c)
                db.add(account)
                db.flush()
                coa_map[c["account_code"]] = account
            else:
                coa_map[c["account_code"]] = existing_account
        db.commit()

        # 4. Seed Cash Accounts
        cash_accounts_data = [
            {"account_code": "CASH_MAIN", "account_name": "Cash Counter 1 (Vault Safe)", "account_type": "CASH", "gl_code": "1010"},
            {"account_code": "BANK_BRAC", "account_name": "BRAC Bank Current A/C", "account_type": "BANK", "gl_code": "1020"},
            {"account_code": "MFS_BKASH", "account_name": "bKash Business Merchant", "account_type": "MFS", "gl_code": "1025"},
        ]

        for ca in cash_accounts_data:
            existing_ca = db.query(CashAccount).filter_by(account_code=ca["account_code"]).first()
            if not existing_ca:
                gl_acc = coa_map.get(ca["gl_code"])
                if gl_acc:
                    db.add(
                        CashAccount(
                            account_code=ca["account_code"],
                            account_name=ca["account_name"],
                            account_type=ca["account_type"],
                            gl_account_id=gl_acc.id,
                            current_balance=Decimal("0.00"),
                        )
                    )
        db.commit()

        # 5. Seed Initial Currency Inventory (MYR)
        myr_inventory = db.query(CurrencyInventory).filter_by(currency_code="MYR").first()
        if not myr_inventory:
            db.add(
                CurrencyInventory(
                    currency_code="MYR",
                    total_quantity=Decimal("0.0000"),
                    weighted_average_cost=Decimal("0.0000"),
                    total_valuation_bdt=Decimal("0.00"),
                )
            )
            db.commit()

        # 6. Seed Default Exchange Rates (Purchase: 300, Selling: 310)
        rate = db.query(ExchangeRate).filter_by(currency_code="MYR", is_active=True).first()
        if not rate:
            db.add(
                ExchangeRate(
                    currency_code="MYR",
                    default_purchase_rate=Decimal("300.0000"),
                    default_selling_rate=Decimal("310.0000"),
                    effective_from=datetime.now(timezone.utc),
                    is_active=True,
                    created_by_id=admin_user.id,
                )
            )
            db.commit()

        # 7. Seed Company Settings
        settings_record = db.query(CompanySettings).first()
        if not settings_record:
            db.add(
                CompanySettings(
                    company_name="Al-Amin Foreign Currency Exchange Ltd.",
                    base_currency="BDT",
                    primary_foreign_currency="MYR",
                    phone="+880 1711-234567",
                    email="info@alaminforex.com.bd",
                    address="Level 4, City Centre, Motijheel Commercial Area, Dhaka-1000, Bangladesh",
                    trade_license_number="TRAD/DNCC/089211/2026",
                    timezone="Asia/Dhaka",
                    receipt_footer_note="Government Approved Money Exchange Enterprise. Please inspect banknotes and currency before departure.",
                )
            )
            db.commit()

        # 8. Seed Expense Categories
        categories_data = [
            {"name": "Office Rent", "gl_code": "6010", "description": "Monthly office premise lease"},
            {"name": "Employee Salaries & Allowances", "gl_code": "6020", "description": "Monthly wages, bonuses, and allowances"},
            {"name": "Electricity & Utilities", "gl_code": "6030", "description": "Power bills and building utility charges"},
            {"name": "Internet & Communication", "gl_code": "6040", "description": "Broadband, corporate mobiles, and server hosting"},
            {"name": "Conveyance & Local Travel", "gl_code": "6050", "description": "Cash courier and operational transport"},
            {"name": "Bank Charges & Fees", "gl_code": "6060", "description": "Wire transfer, cheque book, and banking commissions"},
            {"name": "Office Maintenance & Stationery", "gl_code": "6070", "description": "Stationery, receipt printer rolls, security maintenance"},
            {"name": "Cash Shortage Loss", "gl_code": "6080", "description": "End-of-day teller drawer shortage write-off"},
            {"name": "Miscellaneous Expenses", "gl_code": "6090", "description": "General sundry operational expenses"},
        ]

        for cat in categories_data:
            existing_cat = db.query(ExpenseCategory).filter_by(name=cat["name"]).first()
            if not existing_cat:
                gl_acc = coa_map.get(cat["gl_code"])
                if gl_acc:
                    db.add(
                        ExpenseCategory(
                            name=cat["name"],
                            gl_account_id=gl_acc.id,
                            description=cat["description"],
                        )
                    )
        db.commit()

        print("Database seeded successfully with initial chart of accounts, users, cash accounts, and settings!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
