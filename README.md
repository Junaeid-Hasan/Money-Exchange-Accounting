# Foreign Currency Exchange Management & Accounting System
### Enterprise-Grade Financial ERP for Money Exchange Companies in Bangladesh (MYR - BDT)

---

## 1. System Overview

This application is a production-ready, full-stack Foreign Currency Exchange Management and Accounting System tailored for money exchange companies operating in Bangladesh. 

The primary business activity is purchasing Malaysian Ringgit (**MYR**) from customers and selling **MYR** to other customers in exchange for Bangladeshi Taka (**BDT**). The company independently sets and controls its own purchase and selling exchange rates without external API dependencies.

Built as an **ERP-grade financial engine**, the system provides:
- **Customer Relationship & Ledger Management**: Individual client profiles, separate trade debtor (AR) and trade creditor (AP) tracking without illegal automatic offsetting.
- **Company-Controlled Exchange Rates**: Instant snapshotting of rates on transactions with complete historical rate audit trails.
- **Perpetual Moving Weighted Average Cost (WAC)**: Authoritative inventory costing engine with row-level locking (`SELECT ... FOR UPDATE`) and database-level negative stock prevention.
- **True Double-Entry Bookkeeping**: Automated creation of balanced general ledger journal entries ($\sum \text{Debits} == \sum \text{Credits}$) for every purchase, sale, installment, contra transfer, expense, and daily cash reconciliation.
- **GAAP/IFRS Financial Statements**: Live Balance Sheet (Assets = Liabilities + Equity), Accrual Profit & Loss Statement, Cash Flow Statement, and General Ledger Trial Balance.
- **Multi-Tender Cash & Treasury**: Safe vault cash in hand, commercial bank checking accounts, and mobile financial services (bKash/Nagad) with end-of-day drawer discrepancy tracking.
- **Professional Exports**: ReportLab PDF transaction receipts, customer running ledgers, and OpenPyXL Excel reports.

---

## 2. Technology Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, Alembic.
- **Database**: PostgreSQL 16+ (Production/Docker) with SQLite support for lightweight local development. All monetary calculations use `NUMERIC(18, 4)` and `NUMERIC(18, 2)` (zero floating-point drift).
- **Frontend**: Server-Side Rendered (SSR) Jinja2, Bootstrap 5, Bootstrap Icons, Chart.js for real-time analytics, and responsive print stylesheets.
- **Reporting**: ReportLab (PDF) and OpenPyXL (Excel).
- **Security & RBAC**: Passlib/bcrypt password hashing, HTTP-only secure cookie session tokens with JWT verification, role-based authorization (`ADMIN`, `ACCOUNTANT`, `STAFF`), and comprehensive audit logging.
- **DevOps**: Docker, Docker Compose, automated database seeding and migration scripts.

---

## 3. Financial & Accounting Methodology

### 3.1 Perpetual Moving Weighted Average Cost (WAC)
On every MYR purchase:
$$\text{New WAC} = \frac{\text{Previous Valuation} + (\text{New MYR Qty} \times \text{Purchase Rate})}{\text{Previous MYR Qty} + \text{New MYR Qty}}$$

On every MYR sale:
$$\text{COGS} = \text{Sold MYR Qty} \times \text{Current Moving WAC}$$
$$\text{Inventory Valuation}_{\text{new}} = \text{Inventory Valuation}_{\text{old}} - \text{COGS}$$
*(Moving WAC is preserved on a sale).*

### 3.2 Accrual Profit Calculation
$$\text{Transaction Gross Profit} = \text{Sales Revenue} - \text{COGS}$$
$$\text{Period Net Operating Profit} = \text{Gross Profit} + \text{Other Income} - \text{Operating Expenses}$$
*Note: Collecting old receivables increases cash, not profit. Cash movements and accrual earnings are strictly separated.*

### 3.3 Non-Destructive Financial Audit Trail
Posted transactions are **never deleted or silently modified**. Any correction or voiding produces counter-balancing reversal journal entries and inventory adjustments.

---

## 4. Default Seed Credentials

| Role | Username | Default Password | Privileges |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full access, settings, rate management, user management, voiding |
| **Cashier / Staff** | `staff` | `staff123` | Counter transactions (buy/sell MYR), customers, installment collections |

---

## 5. Quickstart Guide (Local Development)

### Prerequisites
- Python 3.10+ (Tested on Python 3.12 & 3.14)
- Git

### Installation
```bash
# 1. Clone repository and navigate to folder
cd Money-Exchange-Accounting

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install production dependencies
pip install -r requirements.txt

# 4. Initialize database schema via Alembic migrations
alembic upgrade head

# 5. Populate initial Chart of Accounts, users, and default rates
python -m app.seed

# (Optional) Populate sample demo transactions
python -m app.demo_data

# 6. Start development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at `http://localhost:8000`. Log in using `admin` / `admin123`.

---

## 6. Docker & Production Deployment

The project includes a production-grade `docker-compose.yml` configured with PostgreSQL 16:

```bash
# Build and run containers in detached mode
docker-compose up -d --build

# View container logs
docker-compose logs -f app

# Run migrations inside container
docker-compose exec app alembic upgrade head

# Seed initial admin & Chart of Accounts
docker-compose exec app python -m app.seed
```

Access the production instance at `http://localhost:8000`.

---

## 7. Automated Testing Suite

The application includes a rigorous automated test suite testing the exact specifications of currency exchange accounting:

```bash
# Run full pytest suite with verbose output
python -m pytest tests/ -v
```

### Verified Test Cases:
1. `test_purchase_and_installment_lifecycle`: Verifies purchase of 100 MYR @ ৳300 with ৳20,000 paid, followed by installments of ৳5,000 + ৳5,000 to fully settle accounts payable.
2. `test_sales_and_collection_lifecycle`: Verifies sale of 100 MYR @ ৳310 with ৳21,000 paid, followed by remaining ৳10,000 collection to settle accounts receivable.
3. `test_inventory_moving_wac_and_valuation`: Validates perpetual moving WAC (Purchase 100 @ ৳300 + Purchase 100 @ ৳320 -> WAC = ৳310; Sale of 50 MYR leaves 150 MYR valued at ৳46,500).
4. `test_gross_profit_calculation`: Validates gross profit of ৳1,000 on 100 MYR bought @ ৳300 and sold @ ৳310.
5. `test_double_entry_balance_sheet_and_trial_balance`: Validates trial balance ($\sum \text{Debits} == \sum \text{Credits}$) and Balance Sheet ($A = L + E$).
6. `test_payment_does_not_create_duplicate_revenue`: Confirms collection of receivables does not alter sales revenue.
7. `test_negative_inventory_prevention`: Ensures attempts to sell more than available inventory are rejected.
8. `test_rate_modification_does_not_alter_past_transactions`: Guarantees historical transactions preserve their original exchange rates.
9. `test_transaction_reversal_integrity`: Tests counter-reversal journal entries and inventory recovery.
10. `test_api_chart_data_and_web_routes`: Validates all UI and analytics JSON endpoints.
11. `test_pdf_and_excel_exports`: Verifies ReportLab PDF receipts, customer statements, balance sheets, and Excel spreadsheets.

---

## 8. Database Backup & Restore

### PostgreSQL Backup
```bash
docker exec -t money_exchange_db pg_dump -U postgres -F c money_exchange_db > backup_$(date +%Y%m%d).dump
```

### PostgreSQL Restore
```bash
docker exec -i money_exchange_db pg_restore -U postgres -d money_exchange_db --clean < backup_20261118.dump
```
