from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.database import get_db
from app.models import CashAccount, CashMovement, User
from app.dependencies import get_current_user
from app.services.cash_service import transfer_cash_funds, reconcile_daily_cash
from app.templates import render_template

router = APIRouter(prefix="/cash-bank", tags=["Cash & Bank"])


@router.get("", response_class=HTMLResponse)
def cash_bank_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cash_accounts = db.query(CashAccount).all()
    total_cash = db.query(func.coalesce(func.sum(CashAccount.current_balance), Decimal("0.00"))).scalar()
    recent_movements = db.query(CashMovement).order_by(desc(CashMovement.created_at)).limit(50).all()

    return render_template(
        request,
        "cash_bank/index.html",
        {
            "current_user": current_user,
            "active_page": "cash_bank",
            "cash_accounts": cash_accounts,
            "total_cash": total_cash,
            "recent_movements": recent_movements,
            "today_str": date.today().isoformat(),
        },
    )


@router.post("/transfer")
def transfer_post(
    request: Request,
    from_account_id: str = Form(...),
    to_account_id: str = Form(...),
    amount: Decimal = Form(...),
    transfer_date: date = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transfer_cash_funds(
        db=db,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amount,
        transfer_date=transfer_date,
        user_id=current_user.id,
        notes=notes,
    )
    return RedirectResponse(url="/cash-bank", status_code=302)


@router.post("/reconcile")
def reconcile_post(
    request: Request,
    cash_account_id: str = Form(...),
    reconciliation_date: date = Form(...),
    physical_balance: Decimal = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reconcile_daily_cash(
        db=db,
        cash_account_id=cash_account_id,
        reconciliation_date=reconciliation_date,
        physical_balance=physical_balance,
        user_id=current_user.id,
        notes=notes,
    )
    return RedirectResponse(url="/cash-bank", status_code=302)
