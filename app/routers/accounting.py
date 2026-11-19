from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import ChartOfAccount, JournalEntry, User
from app.dependencies import get_current_user
from app.services.accounting_service import get_trial_balance
from app.templates import render_template

router = APIRouter(prefix="/accounting", tags=["Accounting"])


@router.get("/chart-of-accounts", response_class=HTMLResponse)
def chart_of_accounts_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = db.query(ChartOfAccount).order_by(ChartOfAccount.account_code).all()
    return render_template(
        request,
        "accounting/chart_of_accounts.html",
        {
            "current_user": current_user,
            "active_page": "coa",
            "accounts": accounts,
        },
    )


@router.get("/journal-entries", response_class=HTMLResponse)
def journal_entries_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = db.query(JournalEntry).order_by(desc(JournalEntry.entry_date), desc(JournalEntry.created_at)).limit(100).all()
    return render_template(
        request,
        "accounting/journal_entries.html",
        {
            "current_user": current_user,
            "active_page": "journal",
            "entries": entries,
        },
    )


@router.get("/trial-balance", response_class=HTMLResponse)
def trial_balance_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tb = get_trial_balance(db)
    return render_template(
        request,
        "accounting/trial_balance.html",
        {
            "current_user": current_user,
            "active_page": "trial_balance",
            "trial_balance": tb,
        },
    )
