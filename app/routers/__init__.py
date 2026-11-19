from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.customers import router as customers_router
from app.routers.rates import router as rates_router
from app.routers.transactions import router as transactions_router
from app.routers.payments import router as payments_router
from app.routers.inventory import router as inventory_router
from app.routers.expenses import router as expenses_router
from app.routers.cash_bank import router as cash_bank_router
from app.routers.accounting import router as accounting_router
from app.routers.reports import router as reports_router
from app.routers.settings import router as settings_router
from app.routers.users import router as users_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "customers_router",
    "rates_router",
    "transactions_router",
    "payments_router",
    "inventory_router",
    "expenses_router",
    "cash_bank_router",
    "accounting_router",
    "reports_router",
    "settings_router",
    "users_router",
]
