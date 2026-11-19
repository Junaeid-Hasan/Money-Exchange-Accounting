from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.dependencies import get_current_user, require_admin
from app.services.rate_service import (
    get_current_exchange_rate,
    update_exchange_rates,
    get_rate_history,
)
from app.templates import render_template

router = APIRouter(prefix="/rates", tags=["Exchange Rates"])


@router.get("", response_class=HTMLResponse)
def rates_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_rate = get_current_exchange_rate(db, "MYR")
    rate_history = get_rate_history(db, "MYR", limit=50)

    return render_template(
        request,
        "rates/index.html",
        {
            "current_user": current_user,
            "active_page": "rates",
            "current_rate": current_rate,
            "rate_history": rate_history,
        },
    )


@router.post("/update")
def rates_update_post(
    request: Request,
    purchase_rate: Decimal = Form(...),
    selling_rate: Decimal = Form(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    update_exchange_rates(
        db=db,
        purchase_rate=purchase_rate,
        selling_rate=selling_rate,
        user_id=admin_user.id,
        currency_code="MYR",
    )
    return RedirectResponse(url="/rates", status_code=302)
