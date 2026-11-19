from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.database import get_db
from app.models import Expense, ExpenseCategory, CashAccount, User
from app.dependencies import get_current_user, require_admin
from app.services.expense_service import create_expense, void_expense
from app.templates import render_template

router = APIRouter(prefix="/expenses", tags=["Expenses"])


@router.get("", response_class=HTMLResponse)
def expenses_list_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expenses = db.query(Expense).order_by(desc(Expense.expense_date), desc(Expense.created_at)).all()
    categories = db.query(ExpenseCategory).order_by(ExpenseCategory.name).all()
    cash_accounts = db.query(CashAccount).all()

    total_exp = db.query(func.coalesce(func.sum(Expense.amount_bdt), Decimal("0.00"))).filter(
        Expense.status == "POSTED"
    ).scalar()

    return render_template(
        request,
        "expenses/list.html",
        {
            "current_user": current_user,
            "active_page": "expenses",
            "expenses": expenses,
            "categories": categories,
            "cash_accounts": cash_accounts,
            "total_expenses_bdt": total_exp,
            "total_count": len(expenses),
            "today_str": date.today().isoformat(),
        },
    )


@router.post("/create")
def expense_create_post(
    request: Request,
    category_id: str = Form(...),
    amount: Decimal = Form(...),
    cash_account_id: str = Form(...),
    expense_date: date = Form(...),
    description: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    create_expense(
        db=db,
        category_id=category_id,
        amount_bdt=amount,
        cash_account_id=cash_account_id,
        expense_date=expense_date,
        description=description,
        created_by_id=current_user.id,
    )
    return RedirectResponse(url="/expenses", status_code=302)


@router.post("/{expense_id}/void")
def expense_void_post(
    expense_id: str,
    reason: str = Form("Voided by administrator"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    void_expense(db=db, expense_id=expense_id, reason=reason, user_id=admin_user.id)
    return RedirectResponse(url="/expenses", status_code=302)
