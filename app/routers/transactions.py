from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.database import get_db
from app.models import (
    Transaction,
    Customer,
    CashAccount,
    CurrencyInventory,
    CompanySettings,
    User,
)
from app.dependencies import get_current_user, require_admin
from app.services.rate_service import get_current_exchange_rate
from app.services.inventory_service import get_or_create_currency_inventory
from app.services.transaction_service import (
    create_purchase_transaction,
    create_sales_transaction,
    void_cancel_transaction,
)
from app.services.export_service import generate_receipt_pdf, generate_transactions_excel
from app.templates import render_template

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("", response_class=HTMLResponse)
def transactions_list_view(
    request: Request,
    search: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Transaction)
    if type:
        query = query.filter(Transaction.transaction_type == type)
    if status:
        query = query.filter(Transaction.payment_status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.join(Customer).filter(
            or_(
                Transaction.transaction_number.ilike(term),
                Customer.full_name.ilike(term),
                Customer.phone_number.ilike(term),
            )
        )

    total_count = query.count()
    txs = query.order_by(desc(Transaction.transaction_date)).limit(100).all()

    return render_template(
        request,
        "transactions/list.html",
        {
            "current_user": current_user,
            "active_page": "transactions",
            "transactions": txs,
            "total_count": total_count,
            "search": search,
            "selected_type": type,
            "selected_status": status,
        },
    )


@router.get("/purchase", response_class=HTMLResponse)
def purchase_form_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    customers = db.query(Customer).filter(Customer.is_archived == False).order_by(Customer.full_name).all()
    cash_accounts = db.query(CashAccount).all()
    default_rate = get_current_exchange_rate(db, "MYR")

    return render_template(
        request,
        "transactions/purchase_form.html",
        {
            "current_user": current_user,
            "active_page": "purchase",
            "customers": customers,
            "cash_accounts": cash_accounts,
            "default_rate": default_rate,
            "error": None,
        },
    )


@router.post("/purchase")
def purchase_post(
    request: Request,
    customer_id: str = Form(...),
    myr_quantity: Decimal = Form(...),
    purchase_rate: Decimal = Form(...),
    initial_payment: Decimal = Form(Decimal("0.00")),
    cash_account_id: str = Form(...),
    payment_method: str = Form("CASH"),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        tx = create_purchase_transaction(
            db=db,
            customer_id=customer_id,
            myr_quantity=myr_quantity,
            purchase_rate=purchase_rate,
            initial_payment=initial_payment,
            cash_account_id=cash_account_id,
            payment_method=payment_method,
            created_by_id=current_user.id,
            notes=notes,
        )
        return RedirectResponse(url=f"/transactions/{tx.id}", status_code=302)
    except Exception as e:
        customers = db.query(Customer).filter(Customer.is_archived == False).order_by(Customer.full_name).all()
        cash_accounts = db.query(CashAccount).all()
        default_rate = get_current_exchange_rate(db, "MYR")
        return render_template(
            request,
            "transactions/purchase_form.html",
            {
                "current_user": current_user,
                "active_page": "purchase",
                "customers": customers,
                "cash_accounts": cash_accounts,
                "default_rate": default_rate,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/sales", response_class=HTMLResponse)
def sales_form_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    customers = db.query(Customer).filter(Customer.is_archived == False).order_by(Customer.full_name).all()
    cash_accounts = db.query(CashAccount).all()
    default_rate = get_current_exchange_rate(db, "MYR")
    inv = get_or_create_currency_inventory(db, "MYR")

    return render_template(
        request,
        "transactions/sales_form.html",
        {
            "current_user": current_user,
            "active_page": "sales",
            "customers": customers,
            "cash_accounts": cash_accounts,
            "default_rate": default_rate,
            "inventory": inv,
            "error": None,
        },
    )


@router.post("/sales")
def sales_post(
    request: Request,
    customer_id: str = Form(...),
    myr_quantity: Decimal = Form(...),
    selling_rate: Decimal = Form(...),
    initial_payment: Decimal = Form(Decimal("0.00")),
    cash_account_id: str = Form(...),
    payment_method: str = Form("CASH"),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        tx = create_sales_transaction(
            db=db,
            customer_id=customer_id,
            myr_quantity=myr_quantity,
            selling_rate=selling_rate,
            initial_payment=initial_payment,
            cash_account_id=cash_account_id,
            payment_method=payment_method,
            created_by_id=current_user.id,
            notes=notes,
        )
        return RedirectResponse(url=f"/transactions/{tx.id}", status_code=302)
    except Exception as e:
        customers = db.query(Customer).filter(Customer.is_archived == False).order_by(Customer.full_name).all()
        cash_accounts = db.query(CashAccount).all()
        default_rate = get_current_exchange_rate(db, "MYR")
        inv = get_or_create_currency_inventory(db, "MYR")
        return render_template(
            request,
            "transactions/sales_form.html",
            {
                "current_user": current_user,
                "active_page": "sales",
                "customers": customers,
                "cash_accounts": cash_accounts,
                "default_rate": default_rate,
                "inventory": inv,
                "error": str(e),
            },
            status_code=400,
        )


@router.get("/{tx_id}", response_class=HTMLResponse)
def transaction_detail_view(
    tx_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = db.query(Transaction).filter_by(id=tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    cash_accounts = db.query(CashAccount).all()

    return render_template(
        request,
        "transactions/detail.html",
        {
            "current_user": current_user,
            "active_page": "transactions",
            "tx": tx,
            "cash_accounts": cash_accounts,
        },
    )


@router.get("/{tx_id}/receipt", response_class=HTMLResponse)
def transaction_receipt_view(
    tx_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = db.query(Transaction).filter_by(id=tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    settings = db.query(CompanySettings).first()

    return render_template(
        request,
        "transactions/receipt.html",
        {
            "current_user": current_user,
            "active_page": "transactions",
            "tx": tx,
            "settings": settings,
        },
    )


@router.get("/{tx_id}/receipt/pdf")
def transaction_receipt_pdf(
    tx_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = db.query(Transaction).filter_by(id=tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
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
        "receipt_title": "CURRENCY PURCHASE RECEIPT" if tx.transaction_type == "PURCHASE" else "CURRENCY SALES RECEIPT",
        "receipt_number": tx.transaction_number,
        "transaction_number": tx.transaction_number,
        "date": tx.transaction_date.strftime("%Y-%m-%d %I:%M %p"),
        "customer_name": tx.customer.full_name,
        "customer_phone": tx.customer.phone_number,
        "staff_name": tx.created_by_user.full_name,
        "payment_method": tx.payment_method or "Cash",
        "items": [
            {
                "description": f"{'Sold' if tx.transaction_type == 'PURCHASE' else 'Purchased'} Malaysian Ringgit (MYR)",
                "detail": f"{tx.myr_quantity:,.2f} MYR @ ৳{tx.exchange_rate:,.4f}",
                "amount": tx.total_amount_bdt,
            }
        ],
        "total_bdt": tx.total_amount_bdt,
        "paid_bdt": tx.paid_amount_bdt,
        "outstanding_bdt": tx.outstanding_amount_bdt,
    }

    pdf_stream = generate_receipt_pdf(company_info, receipt_data)
    return Response(
        content=pdf_stream.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=receipt_{tx.transaction_number}.pdf"},
    )


@router.post("/{tx_id}/cancel")
def transaction_cancel_post(
    tx_id: str,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    void_cancel_transaction(db, transaction_id=tx_id, reason=reason, user_id=admin_user.id)
    return RedirectResponse(url=f"/transactions/{tx_id}", status_code=302)


@router.get("/export/excel")
def transactions_export_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txs = db.query(Transaction).order_by(desc(Transaction.transaction_date)).all()
    excel_stream = generate_transactions_excel(txs)
    return Response(
        content=excel_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=transactions_export.xlsx"},
    )
