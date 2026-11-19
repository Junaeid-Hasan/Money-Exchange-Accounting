from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.dependencies import get_current_user
from app.services.report_service import get_dashboard_summary
from app.templates import render_template

router = APIRouter(tags=["Dashboard"])


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    summary = get_dashboard_summary(db)
    return render_template(
        request,
        "dashboard/index.html",
        {
            "current_user": current_user,
            "active_page": "dashboard",
            "cards": summary["cards"],
            "recent_purchases": summary["recent_purchases"],
            "recent_sales": summary["recent_sales"],
            "recent_payments": summary["recent_payments"],
            "recent_expenses": summary["recent_expenses"],
            "recent_customers": summary["recent_customers"],
            "debtor_customers": summary["debtor_customers"],
            "creditor_customers": summary["creditor_customers"],
            "partially_paid_txs": summary["partially_paid_txs"],
        },
    )
