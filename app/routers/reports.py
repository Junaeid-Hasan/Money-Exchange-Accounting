from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CompanySettings, User
from app.dependencies import get_current_user
from app.services.accounting_service import (
    get_balance_sheet,
    get_profit_and_loss,
    get_cash_flow_statement,
)
from app.services.report_service import (
    get_dashboard_chart_data,
    get_daily_financial_report,
)
from app.services.export_service import generate_balance_sheet_pdf
from app.templates import render_template

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("", response_class=HTMLResponse)
def reports_hub_view(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return render_template(
        request,
        "reports/index.html",
        {
            "current_user": current_user,
            "active_page": "reports",
        },
    )


@router.get("/balance-sheet", response_class=HTMLResponse)
def balance_sheet_view(
    request: Request,
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bs = get_balance_sheet(db, as_of_date=as_of_date)
    return render_template(
        request,
        "reports/balance_sheet.html",
        {
            "current_user": current_user,
            "active_page": "reports",
            "balance_sheet": bs,
        },
    )


@router.get("/balance-sheet/pdf")
def balance_sheet_pdf_download(
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bs = get_balance_sheet(db, as_of_date=as_of_date)
    settings = db.query(CompanySettings).first()
    company_info = {
        "company_name": settings.company_name if settings else "Money Exchange Ltd.",
        "phone": settings.phone if settings else "",
        "email": settings.email if settings else "",
        "address": settings.address if settings else "",
        "trade_license_number": settings.trade_license_number if settings else "",
    }
    pdf_stream = generate_balance_sheet_pdf(company_info, bs)
    return Response(
        content=pdf_stream.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=balance_sheet_{bs['as_of_date']}.pdf"},
    )


@router.get("/profit-loss", response_class=HTMLResponse)
def profit_loss_view(
    request: Request,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pnl = get_profit_and_loss(db, from_date=from_date, to_date=to_date)
    return render_template(
        request,
        "reports/profit_loss.html",
        {
            "current_user": current_user,
            "active_page": "reports",
            "pnl": pnl,
        },
    )


@router.get("/daily", response_class=HTMLResponse)
def daily_report_view(
    request: Request,
    report_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = report_date or date.today()
    rep = get_daily_financial_report(db, target_date=target)
    return render_template(
        request,
        "reports/daily.html",
        {
            "current_user": current_user,
            "active_page": "reports",
            "report": rep,
        },
    )
