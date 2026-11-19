from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.dependencies import get_current_user
from app.services.inventory_service import (
    get_or_create_currency_inventory,
    get_inventory_summary,
)
from app.templates import render_template

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_class=HTMLResponse)
def inventory_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inv = get_or_create_currency_inventory(db, "MYR")
    summary = get_inventory_summary(db, "MYR")

    return render_template(
        request,
        "inventory/index.html",
        {
            "current_user": current_user,
            "active_page": "inventory",
            "inventory": inv,
            "summary": summary,
        },
    )
