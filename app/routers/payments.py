from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.database import get_db
from app.models import Payment, Customer, Transaction, CompanySettings, User
from app.dependencies import get_current_user
from app.services.payment_service import (
    record_incoming_payment,
    record_outgoing_payment,
)
from app.services.export_service import generate_receipt_pdf
from app.templates import render_template

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("", response_class=HTMLResponse)
def payments_list_view(
    request: Request,
    search: Optional[str] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Payment)
    if type:
        query = query.filter(Payment.payment_type == type)
    if search:
        term = f"%{search.strip()}%"
        query = query.join(Customer).filter(
            or_(
                Payment.payment_number.ilike(term),
                Customer.full_name.ilike(term),
            )
        )

    total_count = query.count()
    payments = query.order_by(desc(Payment.payment_date)).limit(100).all()

    return render_template(
        request,
        "payments/list.html",
        {
            "current_user": current_user,
            "active_page": "payments",
            "payments": payments,
            "total_count": total_count,
            "search": search,
            "selected_type": type,
        },
    )


@router.post("/record")
def payment_record_post(
    request: Request,
    transaction_id: str = Form(...),
    amount: Decimal = Form(...),
    cash_account_id: str = Form(...),
    payment_method: str = Form("CASH"),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = db.query(Transaction).filter_by(id=transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if tx.transaction_type == "SALE":
        record_incoming_payment(
            db=db,
            transaction_id=tx.id,
            amount=amount,
            cash_account_id=cash_account_id,
            payment_method=payment_method,
            created_by_id=current_user.id,
            notes=notes,
        )
    else:
        record_outgoing_payment(
            db=db,
            transaction_id=tx.id,
            amount=amount,
            cash_account_id=cash_account_id,
            payment_method=payment_method,
            created_by_id=current_user.id,
            notes=notes,
        )

    return RedirectResponse(url=f"/transactions/{tx.id}", status_code=302)


@router.get("/{payment_id}/receipt/pdf")
def payment_receipt_pdf(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter_by(id=payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    settings = db.query(CompanySettings).first()

    company_info = {
        "company_name": settings.company_name if settings else "Money Exchange Ltd.",
        "phone": settings.phone if settings else "",
        "email": settings.email if settings else "",
        "address": settings.address if settings else "",
        "trade_license_number": settings.trade_license_number if settings else "",
        "receipt_footer_note": settings.receipt_footer_note if settings else "",
    }

    receipt_data = {
        "receipt_title": "OFFICIAL PAYMENT SETTLEMENT RECEIPT",
        "receipt_number": payment.payment_number,
        "transaction_number": payment.transaction.transaction_number,
        "date": payment.payment_date.strftime("%Y-%m-%d %I:%M %p"),
        "customer_name": payment.customer.full_name,
        "customer_phone": payment.customer.phone_number,
        "staff_name": payment.created_by_user.full_name,
        "payment_method": payment.payment_method,
        "items": [
            {
                "description": f"Installment payment for {payment.transaction.transaction_number}",
                "detail": payment.reference_note or "Receivable / Payable settlement",
                "amount": payment.amount_bdt,
            }
        ],
        "total_bdt": payment.amount_bdt,
        "paid_bdt": payment.amount_bdt,
        "outstanding_bdt": payment.transaction.outstanding_amount_bdt,
    }

    pdf_stream = generate_receipt_pdf(company_info, receipt_data)
    return Response(
        content=pdf_stream.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=receipt_{payment.payment_number}.pdf"},
    )
