from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, CompanySettings
from app.dependencies import get_current_user
from app.services.customer_service import (
    list_customers,
    create_customer,
    update_customer,
    get_customer_profile_summary,
)
from app.services.payment_service import record_mutual_balance_settlement
from app.services.export_service import generate_customer_statement_pdf
from app.templates import render_template

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_class=HTMLResponse)
def customers_list_view(
    request: Request,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    customers, total_count = list_customers(db, search_query=search)
    return render_template(
        request,
        "customers/list.html",
        {
            "current_user": current_user,
            "active_page": "customers",
            "customers": customers,
            "total_count": total_count,
            "search_query": search,
        },
    )


@router.post("/create")
def customer_create_post(
    request: Request,
    full_name: str = Form(...),
    phone_number: str = Form(...),
    national_id: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    create_customer(
        db=db,
        full_name=full_name,
        phone_number=phone_number,
        national_id=national_id,
        address=address,
        notes=notes,
        user_id=current_user.id,
    )
    return RedirectResponse(url="/customers", status_code=302)


@router.get("/{customer_id}", response_class=HTMLResponse)
def customer_detail_view(
    customer_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    summary = get_customer_profile_summary(db, customer_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Customer not found")

    return render_template(
        request,
        "customers/detail.html",
        {
            "current_user": current_user,
            "active_page": "customers",
            "summary": summary,
        },
    )


@router.post("/{customer_id}/update")
def customer_update_post(
    customer_id: str,
    full_name: str = Form(...),
    phone_number: str = Form(...),
    national_id: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_customer(
        db=db,
        customer_id=customer_id,
        full_name=full_name,
        phone_number=phone_number,
        national_id=national_id,
        address=address,
        notes=notes,
        user_id=current_user.id,
    )
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=302)


@router.post("/{customer_id}/mutual-settlement")
def customer_mutual_settlement_post(
    customer_id: str,
    amount: Decimal = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record_mutual_balance_settlement(
        db=db,
        customer_id=customer_id,
        amount=amount,
        created_by_id=current_user.id,
        notes=notes,
    )
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=302)


@router.get("/{customer_id}/statement/pdf")
def customer_statement_pdf_download(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    summary = get_customer_profile_summary(db, customer_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Customer not found")

    settings = db.query(CompanySettings).first()
    company_info = {
        "company_name": settings.company_name if settings else "Money Exchange Ltd.",
        "phone": settings.phone if settings else "",
        "email": settings.email if settings else "",
        "address": settings.address if settings else "",
        "trade_license_number": settings.trade_license_number if settings else "",
    }

    pdf_stream = generate_customer_statement_pdf(company_info, summary)
    return Response(
        content=pdf_stream.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=statement_{summary['customer'].customer_code}.pdf"},
    )
