from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CompanySettings, User
from app.dependencies import require_admin
from app.templates import render_template

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_class=HTMLResponse)
def settings_view(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    settings = db.query(CompanySettings).first()
    return render_template(
        request,
        "settings/index.html",
        {
            "current_user": admin_user,
            "active_page": "settings",
            "settings": settings,
            "success": request.query_params.get("success"),
        },
    )


@router.post("/update")
def settings_update_post(
    request: Request,
    company_name: str = Form(...),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    trade_license_number: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    receipt_footer_note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    settings = db.query(CompanySettings).first()
    if not settings:
        settings = CompanySettings()
        db.add(settings)

    settings.company_name = company_name.strip()
    settings.phone = phone.strip() if phone else None
    settings.email = email.strip() if email else None
    settings.trade_license_number = trade_license_number.strip() if trade_license_number else None
    settings.address = address.strip() if address else None
    settings.receipt_footer_note = receipt_footer_note.strip() if receipt_footer_note else None

    db.commit()
    return RedirectResponse(url="/settings?success=1", status_code=302)
