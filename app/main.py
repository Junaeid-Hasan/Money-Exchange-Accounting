from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, get_db
import app.models  # Load metadata
from app.seed import seed_database
from app.routers import (
    auth_router,
    dashboard_router,
    customers_router,
    rates_router,
    transactions_router,
    payments_router,
    inventory_router,
    expenses_router,
    cash_bank_router,
    accounting_router,
    reports_router,
    settings_router,
    users_router,
)
from app.services.report_service import get_dashboard_chart_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database is seeded on startup
    try:
        seed_database()
    except Exception as e:
        print(f"Startup seed notice: {e}")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Foreign Currency Exchange Management & Accrual Accounting System",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include Application Routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(customers_router)
app.include_router(rates_router)
app.include_router(transactions_router)
app.include_router(payments_router)
app.include_router(inventory_router)
app.include_router(expenses_router)
app.include_router(cash_bank_router)
app.include_router(accounting_router)
app.include_router(reports_router)
app.include_router(settings_router)
app.include_router(users_router)


# API endpoint for Chart.js
@app.get("/api/v1/reports/chart-data", tags=["API Analytics"])
def chart_data_api(days: int = 14, db: Session = Depends(get_db)):
    return get_dashboard_chart_data(db, days=days)


# Global Exception Handler for Authentication redirects
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    accept = request.headers.get("Accept", "")
    if exc.status_code == status.HTTP_401_UNAUTHORIZED and "text/html" in accept:
        return RedirectResponse(
            url=f"/auth/login?next={request.url.path}",
            status_code=status.HTTP_302_FOUND
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers or {}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
